/*
 * A TOS .PRG is a flat image, so everything lands in one output section.
 *
 * The order matters: .data (the variables) comes right behind the boot jump, so PC-relative references to it from
 * the first 32 KB of code stay inside the 68000's signed 16-bit displacement however large the code grows.
 * .stack goes last: it is zeros that nothing needs to reach with a displacement.
 *
 * image_size is the length of the whole image, for Mshrink.
 */
SECTIONS
{
  . = 0;

  .text :
  {
    *(.text.boot)
    *(.data*)
    *(.text)
    *(.text.late)
    *(.rodata*)
    *(.stack*)
    image_size = ABSOLUTE(.);
  }

  /DISCARD/ :
  {
    *(.comment*)
    *(.note*)
    *(.eh_frame*)
  }
}
