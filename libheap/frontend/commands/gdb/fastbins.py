from __future__ import print_function

import sys
import struct

try:
    import gdb
except ImportError:
    print("Not running inside of GDB, exiting...")
    sys.exit()

from libheap.frontend.printutils import print_title
from libheap.frontend.printutils import print_error
from libheap.frontend.printutils import print_value

from libheap.ptmalloc.ptmalloc import ptmalloc

from libheap.ptmalloc.malloc_state import malloc_state
from libheap.ptmalloc.malloc_chunk import malloc_chunk


class fastbins(gdb.Command):
    """Walk and print the fast bins."""

    def __init__(self, debugger=None, version=None):
        super(fastbins, self).__init__("fastbins", gdb.COMMAND_OBSCURE,
                                       gdb.COMPLETE_NONE)

        if debugger is not None:
            self.dbg = debugger
        else:
            print_error("Please specify a debugger")
            sys.exit()

        self.version = version

    def invoke(self, arg, from_tty):
        ptm = ptmalloc(debugger=self.dbg)

        if ptm.SIZE_SZ == 0:
            ptm.set_globals()

        if ptm.SIZE_SZ == 4:
            pad_width = 25
        elif ptm.SIZE_SZ == 8:
            pad_width = 29

        fb_num = None
        if len(arg) == 0:
            # XXX: from old heap command, replace
            main_arena = self.dbg.read_variable("main_arena")
            arena_address = self.dbg.format_address(main_arena.address)
            thread_arena = self.dbg.read_variable("thread_arena")
            arena_address = int(thread_arena)
        else:
            argv = arg.split(" ")
            argv.reverse()
            arena_address = int(argv.pop(), 0)
            if argv:
                fb_num = int(argv.pop())

        print_title("fastbins", end="")

        ar_ptr = malloc_state(arena_address, debugger=self.dbg,
                              version=self.version)
        # 8 bytes into struct malloc_state on both 32/64bit
        # XXX: fixme for glibc <= 2.19 with THREAD_STATS
        fastbinsY = int(ar_ptr.address) + 8
        fb_base = fastbinsY

        for fb in range(0, ptm.NFASTBINS):
            if fb_num is not None:
                fb = fb_num

            offset = int(fb_base + fb * ptm.SIZE_SZ)
            try:
                mem = self.dbg.read_memory(offset, ptm.SIZE_SZ)
                if ptm.SIZE_SZ == 4:
                    fd = struct.unpack("<I", mem)[0]
                elif ptm.SIZE_SZ == 8:
                    fd = struct.unpack("<Q", mem)[0]
            except RuntimeError:
                print_error("Invalid fastbin addr {0:#x}".format(offset))
                return

            print("")
            print("[ fb {} ] ".format(fb), end="")
            print("{:#x}{:>{width}}".format(offset, "-> ", width=5), end="")
            if fd == 0:
                print("[ {:#x} ] ".format(fd), end="")
            else:
                print_value("[ {:#x} ] ".format(fd))

            if fd != 0:  # fastbin is not empty
                fb_size = ((ptm.MIN_CHUNK_SIZE) + (ptm.MALLOC_ALIGNMENT) * fb)
                print("({})".format(int(fb_size)), end="")

                chunk = malloc_chunk(fd, inuse=False, debugger=self.dbg)
                while chunk.fd != 0:
                    if chunk.fd is None:
                        # could not read memory section
                        break

                    print_value("\n{:>{width}} {:#x} {} ".format("[",
                                chunk.fd, "]", width=pad_width))
                    print("({})".format(fb_size), end="")

                    chunk = malloc_chunk(chunk.fd, inuse=False,
                                         debugger=self.dbg)

            if fb_num is not None:  # only print one fastbin
                break

        print("")
