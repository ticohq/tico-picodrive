/*
 * PicoDrive
 * Copyright (C) 2009,2010 notaz
 *
 * This work is licensed under the terms of MAME license.
 * See COPYING file in the top-level directory.
 */
#include <stdio.h>

#include <pico/pico_int.h>
#include "cmn.h"

#if defined(__linux__) && (defined(__aarch64__) || defined(__VFP_FP__))
// might be running on a 64k-page kernel
#define PICO_PAGE_ALIGN 65536
#else
#define PICO_PAGE_ALIGN 4096
#endif
#if defined(__SWITCH__) && defined(__aarch64__)
#include <stdlib.h>
#include <switch.h>
// in .text: executable, and close enough to the C helpers for direct calls
u8 ALIGNED(PICO_PAGE_ALIGN) tcache_default[DRC_TCACHE_SIZE] __attribute__((section(".text")));
ptrdiff_t drc_rw_offset;
int drc_unavailable;
static void *tcache_rw;
static u8 *tcache_fallback;

// A writable view of tcache_default, as flycast maps its code cache on Switch
static int drc_map_rw(void)
{
  int failed;
  if (tcache_rw != NULL)
    return 0;
  virtmemLock();
  tcache_rw = virtmemFindAslr(DRC_TCACHE_SIZE, 0);
  failed = tcache_rw == NULL ||
    R_FAILED(svcMapProcessMemory(tcache_rw, envGetOwnProcessHandle(),
                                 (u64)tcache_default, DRC_TCACHE_SIZE));
  virtmemUnlock();
  if (failed) {
    tcache_rw = NULL;
    return -1;
  }
  drc_rw_offset = (u8 *)tcache_rw - tcache_default;
  return 0;
}

static void drc_unmap_rw(void)
{
  if (tcache_rw == NULL)
    return;
  virtmemLock();
  svcUnmapProcessMemory(tcache_rw, envGetOwnProcessHandle(),
                        (u64)tcache_default, DRC_TCACHE_SIZE);
  virtmemUnlock();
  tcache_rw = NULL;
  drc_rw_offset = 0;
}
#else
u8 ALIGNED(PICO_PAGE_ALIGN) tcache_default[DRC_TCACHE_SIZE];
#endif
u8 *tcache;

void drc_cmn_init(void)
{
  int ret;

#if defined(__SWITCH__) && defined(__aarch64__)
  tcache = tcache_default;
  ret = drc_map_rw();
  elprintf(EL_STATUS, "drc_cmn_init: rx %p rw %p, %zd bytes: %d",
    tcache, tcache_rw, DRC_TCACHE_SIZE, ret);
  if (ret != 0) {
    // No writable view: the interpreter runs. The compiler still emits its
    // helpers at init, so they go to heap memory that is never executed.
    drc_unavailable = 1;
    PicoIn.opt &= ~POPT_EN_DRC;
    if (tcache_fallback == NULL)
      tcache_fallback = malloc(DRC_TCACHE_SIZE);
    tcache = tcache_fallback;
    drc_rw_offset = 0;
  }
  return;
#endif
  tcache = plat_mem_get_for_drc(DRC_TCACHE_SIZE);
  if (tcache == NULL)
    tcache = tcache_default;

  ret = plat_mem_set_exec(tcache, DRC_TCACHE_SIZE);
  elprintf(EL_STATUS, "drc_cmn_init: %p, %zd bytes: %d",
    tcache, DRC_TCACHE_SIZE, ret);

#ifdef __arm__
  if (PicoIn.opt & POPT_EN_DRC)
  {
    static int test_done;
    if (!test_done)
    {
      int *test_out = (void *)tcache;
      int (*testfunc)(void) = (void *)tcache;

      elprintf(EL_STATUS, "testing if we can run recompiled code..");
      *test_out++ = 0xe3a000dd; // mov r0, 0xdd
      *test_out++ = 0xe12fff1e; // bx lr
      cache_flush_d_inval_i(tcache, test_out);

      // we'll usually crash on broken platforms or bad ports,
      // but do a value check too just in case
      ret = testfunc();
      elprintf(EL_STATUS, "test %s.", ret == 0xdd ? "passed" : "failed");
      test_done = 1;
    }
  }
#endif
}

void drc_cmn_cleanup(void)
{
#if defined(__SWITCH__) && defined(__aarch64__)
  drc_unmap_rw();
#endif
}

// vim:shiftwidth=2:expandtab
