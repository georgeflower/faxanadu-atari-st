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
DISK := $(BUILD_DIR)/FAXANADU.st

MAIN_SRC := $(SRC_DIR)/main.s
# main.s .includes the other modules, so one assembler run covers them all.
SOURCES := $(wildcard $(SRC_DIR)/*.s)

.DEFAULT_GOAL := all
.PHONY: all disk check clean

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
disk: all
	$(PYTHON) $(TOOLS_DIR)/make_disk.py $(DISK) $(PRG)

check: all
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py'
	$(PYTHON) $(TOOLS_DIR)/make_prg.py --check $(PRG)

clean:
	rm -rf $(BUILD_DIR)
