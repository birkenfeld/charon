# Testing PLC code.

from charon.sim.st import Var, Struct, Globals, program, \
    array, word, dword, bool, byte, real, string
from charon.sim.funcs import adr, sizeof, memset, memcpy
from random import random


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


class ST_Motor(Struct):
    value = Var(real)
    target = Var(real)
    status = Var(word)
    paramidx = Var(word)
    paramval = Var(real)


class ST_SDI(Struct):
    value = Var(word)


class ST_SDO(Struct):
    value = Var(word)
    target = Var(word)


class ST_ESS_Axis(Struct):
    value = Var(real)
    actVelocity = Var(real)  # 1 extrafloat
    target = Var(real, 4)
    status = Var(word)
    paramidx = Var(word)
    paramval = Var(real)
    extrabits = Var(dword)   # 1. extraDword
    raw_coder = Var(dword)   # 2. extraDword
    raw_motor = Var(dword)   # 3. extraDword (high dword of raw_coder)
    error_code = Var(dword)  # 4. extraword


class Global(Globals):
    fMagic = Var(real, 2015.02, at='%MB0')
    iOffset = Var(dword, 64, at='%MB4')

    stIndexer = Var(ST_Indexer, at='%MB64')

    if_motor = Var(ST_Motor, at='%MB100')
    if_cycle_counter = Var(ST_SDI, at='%MB98')
    if_sd_output = Var(ST_SDO, at='%MB116')
    if_ess_motor = Var(ST_ESS_Axis, at='%MB120')

    Devices = Var(array(ST_DeviceInfo, 1, 4), [
        ST_DeviceInfo(TypCode=0x5008, Name='motor', Offset=100, Unit=0xfd04,
                      Params=[0, 0xc000, 0x000f, 0xf800, 0x001b, 0, 0, 0, 0x200]),
        ST_DeviceInfo(TypCode=0x1201, Name='cycle_counter', Offset=98),
        ST_DeviceInfo(TypCode=0x1602, Name='sd_output', Offset=116),
        ST_DeviceInfo(TypCode=0x7112, Name='ess_motor', Offset=120, Unit=0xfd04,
                      Params=[0, 0xc000, 0x000f, 0xf800, 0x001b, 0, 0, 0, 0x200],
                      Aux=["Aux%d" % d for d in range(7)],
                      AbsMax = 100,
                      AbsMin = 100),
    ])

    sPLCName = Var(string(34), 'Simulator')
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

    g.iCycle += 1

    v.devnum = g.stIndexer.Request & 0xff
    v.infotype = (g.stIndexer.Request >> 8) & 0x7f

    data = g.stIndexer.Data
    if g.stIndexer.Request[[15]] == 0:
        memset(adr(data), 0, sizeof(data))
    else:
        if v.infotype == 127:
            data[1] = g.iCycle
        return

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


@program()
def Implementierung(v):
    def handle_motor(m):
        s = m.status >> 12
        if s == 0:
            m.status = 0x1000
        elif s in [1, 3]:
            if g.iCycle > 30000:
                m.status = 0x3200
            else:
                m.status = 0x1000
        elif s == 5:
            m.status = 0x6000
        elif s == 7:
            m.status = 0x1000
        elif s == 6:
            if m.value == m.target:
                m.status = 0x1000
            else:
                step = 0.001
                if float(m.value) > float(m.target + step):
                    m.value = float(m.value) - step
                elif float(m.value) < float(m.target - step):
                    m.value = float(m.value) + step
                else:
                    m.value = float(m.target)
    handle_motor(g.if_motor)
    lastpos = float(g.if_ess_motor.value)
    handle_motor(g.if_ess_motor)
    # fake extra values.
    m = g.if_ess_motor
    m.actVelocity = m.value - lastpos
    m.extrabits = g.iCycle
    m.raw_coder = int(m.value * 10000 - 5 + 10 * random())
    m.raw_motor = int(m.value * 4000)

    g.if_cycle_counter.value = g.iCycle
    g.if_sd_output.value = g.if_sd_output.target


@program()
def Main(v):
    Indexer()
    Implementierung()
