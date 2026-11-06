BUILD_DIR := build
SRC_DIR := src
TOOLS_DIR := tools
PYTHON ?= python3

TOOLCHAIN_PREFIX ?= m68k-linux-gnu-
AS := $(TOOLCHAIN_PREFIX)as
LD := $(TOOLCHAIN_PREFIX)ld
OBJCOPY := $(TOOLCHAIN_PREFIX)objcopy
NM := $(TOOLCHAIN_PREFIX)nm

ASFLAGS := -m68000 -I $(SRC_DIR)
LDFLAGS := -T link.ld -nostdlib -e _start

ELF := $(BUILD_DIR)/faxanadu_st.elf
BIN := $(BUILD_DIR)/faxanadu_st.bin
PRG := $(BUILD_DIR)/FAXANADU.PRG
OBJ := $(BUILD_DIR)/faxanadu_st.o
LISTING := $(BUILD_DIR)/faxanadu_st.lst
# Disk images are named Fax###.st, ### = the build number = the number of commits on this branch (git rev-list --count HEAD), three digits.
BUILD_NUMBER := $(shell printf '%03d' $$(git rev-list --count HEAD))
DISK := $(BUILD_DIR)/Fax$(BUILD_NUMBER).st
VIEWER_DISK := $(BUILD_DIR)/Fax$(BUILD_NUMBER).st

MAIN_SRC := $(SRC_DIR)/main.s
# main.s .includes the other modules, so one assembler run covers them all.
SOURCES := $(wildcard $(SRC_DIR)/*.s)

.DEFAULT_GOAL := all
.PHONY: all disk viewerdisk check clean

all: $(PRG)

$(OBJ): $(SOURCES)
	@mkdir -p $(BUILD_DIR)
	$(AS) $(ASFLAGS) -al=$(LISTING) -o $@ $(MAIN_SRC)

# The reach check runs on every link: a branch that does not reach wraps silently in GNU as and ld.
$(ELF): $(OBJ) link.ld
	$(LD) $(LDFLAGS) -o $@ $(OBJ)
	$(PYTHON) $(TOOLS_DIR)/check_reach.py --nm $(NM) --listing $(LISTING) $@ $(SOURCES)

$(BIN): $(ELF)
	$(OBJCOPY) -O binary $< $@

$(PRG): $(BIN) $(TOOLS_DIR)/make_prg.py
	$(PYTHON) $(TOOLS_DIR)/make_prg.py $< $@

# A 720 KB floppy image for a Gotek, a real drive or an emulator.
viewerdisk: viewer
	$(PYTHON) $(TOOLS_DIR)/make_disk.py $(VIEWER_DISK) $(VIEWER_PRG)

disk: all
	$(PYTHON) $(TOOLS_DIR)/make_disk.py $(DISK) $(PRG)

check: all
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py'
	$(PYTHON) $(TOOLS_DIR)/make_prg.py --check $(PRG)

clean:
	rm -rf $(BUILD_DIR)

# The overscan test program (a second PRG from src/overscan_test.s). TB_LINE and TB_NOPS tune the timed writes:
#   make overscan TB_LINE=199 TB_NOPS=0 TB_WAIT=50
TB_LINE ?= 199
TB_NOPS ?= 0
TB_WAIT ?= 50
OVERSCAN_PRG := $(BUILD_DIR)/OVERSCAN.PRG
# make overscan OVERSCAN_DEFS="--defsym AUTOEXIT=100" builds a test program that leaves by itself after 100 frames.
OVERSCAN_DEFS ?=
.PHONY: overscan
overscan:
	@mkdir -p $(BUILD_DIR)
	$(AS) -m68000 --defsym TB_LINE=$(TB_LINE) --defsym TB_NOPS=$(TB_NOPS) --defsym TB_WAIT=$(TB_WAIT) $(OVERSCAN_DEFS) -al=$(BUILD_DIR)/overscan.lst -o $(BUILD_DIR)/overscan.o $(SRC_DIR)/overscan_test.s
	$(LD) $(LDFLAGS) -o $(BUILD_DIR)/overscan.elf $(BUILD_DIR)/overscan.o
	$(OBJCOPY) -O binary $(BUILD_DIR)/overscan.elf $(BUILD_DIR)/overscan.bin
	$(PYTHON) $(TOOLS_DIR)/make_prg.py $(BUILD_DIR)/overscan.bin $(OVERSCAN_PRG)

# The viewer: one screen of the game on the ST, from your ROM (ext/Faxanadu_Europe.nes).
#   make viewer AREA=0 SCREEN=1 CAMERA=40
AREA ?= 0
SCREEN ?= 1
CAMERA ?= 40
# the hero: x,y,armour,shield,weapon,frame,faces-left (default: after the castle door, start equipment)
HERO ?= 144,144,0,255,0,0,1
# the HUD drawn first and the state drawn over it: power,magic,experience,gold,seconds
HUD ?= 16,0,0,0,0
HUD2 ?=
VIEWER_DEFS ?=
ROM_FILE ?= ../ext/Faxanadu_Europe.nes
GENERATED := $(BUILD_DIR)/generated
VIEWER_PRG := $(BUILD_DIR)/VIEWER.PRG
.PHONY: viewer sound
# The songs and sound effects come from recording the ROM's own sound engine in the headless NES (tools/refnes; node and npm install
# there). Without them the viewer is built without sound.
sound:
	$(PYTHON) $(TOOLS_DIR)/build_sound.py --record --out $(GENERATED)/sound.bin
viewer:
	@mkdir -p $(BUILD_DIR)
	$(PYTHON) $(TOOLS_DIR)/build_sound.py --record --out $(GENERATED)/sound.bin
	$(PYTHON) $(TOOLS_DIR)/build_assets.py --rom $(ROM_FILE) --area $(AREA) --screen $(SCREEN) --camera $(CAMERA) --hero $(HERO) --hud $(HUD) --hud2 '$(HUD2)' --out $(GENERATED)
	$(AS) -m68000 -I $(GENERATED) -I $(SRC_DIR) $(VIEWER_DEFS) -al=$(BUILD_DIR)/viewer.lst -o $(BUILD_DIR)/viewer.o $(SRC_DIR)/viewer.s
	$(LD) $(LDFLAGS) -o $(BUILD_DIR)/viewer.elf $(BUILD_DIR)/viewer.o
	$(PYTHON) $(TOOLS_DIR)/check_reach.py --nm $(NM) --text-base start --listing $(BUILD_DIR)/viewer.lst $(BUILD_DIR)/viewer.elf $(SRC_DIR)/viewer.s
	$(OBJCOPY) -O binary $(BUILD_DIR)/viewer.elf $(BUILD_DIR)/viewer.bin
	$(PYTHON) $(TOOLS_DIR)/make_prg.py $(BUILD_DIR)/viewer.bin $(VIEWER_PRG)
