# Testing PLC code.

from charon.sim.st import Var, Struct, Globals, program, \
    run, array, word, dword, bool, byte, real, string
from charon.sim.funcs import adr, sizeof, memset, memcpy


class ST_DeviceInfo(Struct):
    TypCode = Var(word, 0)
    Size = Var(word, 0)
    Offset = Var(word, 0)
    Unit = Var(word, 0)
    Flags = Var(dword, 0)
    Params = Var(array(word, 1, 16), [0] * 16)
    Name = Var(string(34))
    Aux = Var(array(string(34), 0, 7))
    AbsMax = Var(real, 3.402823e38)
    AbsMin = Var(real, -3.402823e38)


class ST_Indexer(Struct):
    Request = Var(word, 0)
    Data = Var(array(word, 1, 17))


class Global(Globals):
    fMagic = Var(real, 2015.02, at='%MB0')
    iOffset = Var(word, 64, at='%MB4')

    stIndexer = Var(ST_Indexer, at='%MB64')

    Devices = Var(array(ST_DeviceInfo, 1, 3), [
        ST_DeviceInfo(TypCode=0x5008, Name='motor', Offset=100, Unit=0xfd04,
                      Params=[0, 0xc000, 0x000f, 0xf800, 0x001b, 0, 0, 0, 0x200]),
        ST_DeviceInfo(TypCode=0x1201, Name='rsvd_input'),
        ST_DeviceInfo(TypCode=0x1602, Name='rsvd_output', Offset=136),
    ])

    sPLCName = Var(string(34), 'jemsc')
    sPLCVersion = Var(string(34), '0.0.1alpha')
    iCycle = Var(word, 0)

g = Global()


@program(
    nDevices = Var(word),
    devnum = Var(word),
    infotype = Var(word),
    is_initialized = Var(bool, False),
    itemp = Var(byte),
    tempofs = Var(word))
def Indexer(v):
    if not v.is_initialized:
        v.tempofs = g.iOffset + sizeof(g.stIndexer)
        v.nDevices = sizeof(g.Devices) // sizeof(g.Devices[1])
        v.itemp = 1
        while v.itemp <= v.nDevices:
            dev = g.Devices[v.itemp]
            # for i in range(8):
            dev.Flags[[0]] = len(dev.Aux[0]) > 0
            dev.Flags[[1]] = len(dev.Aux[1]) > 0
            dev.Flags[[2]] = len(dev.Aux[2]) > 0
            dev.Flags[[3]] = len(dev.Aux[3]) > 0
            dev.Flags[[4]] = len(dev.Aux[4]) > 0
            dev.Flags[[5]] = len(dev.Aux[5]) > 0
            dev.Flags[[6]] = len(dev.Aux[6]) > 0
            dev.Flags[[7]] = len(dev.Aux[7]) > 0
            if dev.Size < (dev.TypCode & 0xff) << 1:
                dev.Size = (dev.TypCode & 0xff) << 1
            if dev.Offset == 0:
                dev.Offset = v.tempofs
            else:
                v.tempofs = dev.Offset
            v.tempofs += dev.Size
            v.itemp += 1
        v.is_initialized = True

    if g.fMagic != 2015.02:
        g.fMagic = 2015.02
    if g.iOffset != 64:
        g.iOffset = 64

    v.devnum = g.stIndexer.Request & 0xff
    v.infotype = (g.stIndexer.Request >> 8) & 0x7f

    data = g.stIndexer.Data
    memset(adr(data), 0, sizeof(data))

    if v.devnum == 0:
        if v.infotype == 0:
            data[1] = 0
            data[2] = 0x0000
            data[3] = 0x8000
            data[4] = sizeof(g.stIndexer)
            data[5] = g.iOffset
        elif v.infotype == 1:
            data[1] = sizeof(g.stIndexer)
        elif v.infotype == 4:
            memcpy(adr(data), adr(g.sPLCName),
                   min(sizeof(g.sPLCName), sizeof(data)))
        elif v.infotype == 5:
            memcpy(adr(data), adr(g.sPLCVersion),
                   min(sizeof(g.sPLCVersion), sizeof(data)))
    elif v.devnum <= v.nDevices:
        dev = g.Devices[v.devnum]
        if v.infotype == 0:
            data[1] = dev.TypCode
            data[2] = dev.Size
            data[3] = dev.Offset
            data[4] = dev.Unit
            data[5] = dev.Flags
            data[6] = dev.Flags >> 16
            memcpy(adr(data[7]), adr(dev.AbsMin), sizeof(dev.AbsMin))
            memcpy(adr(data[9]), adr(dev.AbsMax), sizeof(dev.AbsMax))
            memcpy(adr(data[11]), adr(dev.Name),
                   min(sizeof(dev.Name), sizeof(data) - 20))
        elif v.infotype == 1:
            data[1] = dev.Size
        elif v.infotype == 2:
            data[1] = dev.Offset
        elif v.infotype == 3:
            data[1] = dev.Unit
        elif v.infotype == 4:
            memcpy(adr(data), adr(dev.Name),
                   min(sizeof(dev.Name), sizeof(data)))
        elif v.infotype == 15:
            memcpy(adr(data), adr(dev.Params),
                   min(sizeof(dev.Params), sizeof(data)))
        elif v.infotype >= 0x10 and v.infotype <= 0x17:
            memcpy(adr(data), adr(dev.Aux[v.infotype - 0x10]),
                   min(sizeof(dev.Aux[v.infotype - 0x10]), sizeof(data)))

    if v.infotype == 127:
        data[1] = g.iCycle
    g.stIndexer.Request[[15]] = 1
    g.iCycle += 1

    #print(g.stIndexer.Request, data)


@program()
def Implementierung(v):
    pass


@program()
def Main(v):
    Indexer()
    Implementierung()
