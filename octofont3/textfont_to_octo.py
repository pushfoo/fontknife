#!/usr/bin/python3
import fileinput
import sys
import getopt
from collections import deque
from functools import cache
from math import log
from typing import Optional, Iterable

from octofont3.iohelpers import OutputHelper, TextIOBaseSubclass

from octofont3.textfont.parser import TextFontFile


def padded_hex(value: int, num_digits: int = 2) -> str:
    return f"0x{hex(value)[2:].zfill(num_digits)}"


class OctoStream(OutputHelper):
    """
    A helper for printing octo-related statements
    """

    def __init__(self, stream: TextIOBaseSubclass, indent_chars="  "):
        super().__init__(stream)

        self._indent_level = 0
        self._indent_chars = indent_chars
        self.byte_queue = deque()

    def print(self, *objects, sep: str = ' ', end: str = '\n') -> None:
        self.write(self.get_indent_prefix(self._indent_level))
        super().print(*objects, sep=sep, end=end)

    @property
    def indent_level(self) -> int:
        return self._indent_level

    @indent_level.setter
    def indent_level(self, new_level: int = 0):
        if new_level < 0:
            raise ValueError("indent_level must be 0 or greater")
        self._indent_level = new_level

    @cache
    def get_indent_prefix(self, level: int) -> str:
        return self._indent_chars * self._indent_level

    def label(self, label_name: str, end: str = "\n"):
        self.print(f": {label_name}", end=end)

    def multi_statement_line(self, statements: Iterable, sep: Optional[str] = None) -> None:
        """
        Compatibility tool for multiple statements on a single line

        The original implementation had this behavior and we'll duplicate it.

        :param statements:
        :param custom_sep:
        :return:
        """
        sep = sep or self._indent_chars
        self.print(sep.join((str(s) for s in statements)))

    def begin_indented_func(self, label_name):
        self.label(label_name)
        self.indent_level += 1

    def end_indented_func(self) -> None:
        self.print("return")
        self.indent_level -= 1

    @cache
    def pad_for_label_name(self, label_name) -> str:
        return f"{' ' * (len(label_name) + 3)}"

    def queue_data(self, byte_source: Iterable[int]):
        self.byte_queue.extend(byte_source)

    def write_queued_data_with_label(self, label_name: str, max_bytes_per_line: int = 16):
        self.label(label_name, end=' ')
        label_pad = self.pad_for_label_name(label_name)

        byte_queue = self.byte_queue
        line = 0
        num_to_pop = max_bytes_per_line
        while byte_queue:
            num_to_pop = min(max_bytes_per_line, len(byte_queue))
            self.print(' '.join((padded_hex(byte_queue.popleft()) for i in range(num_to_pop))))
            self.print()
            if byte_queue:
                self.print(label_pad, end='')


def emit_octo(stream, font_data: TextFontFile):
    # get the max height and max width of the font?
    # is this really needed? just reparse from it?
    # user COULD edit a font to be bigger...
    font_width = font_data.max_width
    font_height = font_data.max_height

    first_glyph = font_data.first_glyph
    last_glyph = font_data.last_glyph
    glyphs = font_data.glyph
    # print glyphs

    if font_width == 0 or font_height == 0:
        print("Did not find font dimensions")
        sys.exit(2)
    if font_width > 8:
        print("Font width larger than 8 pixels, not yet supported")
        sys.exit(2)
    if font_height > 8:
        print("Font height larger than 8 pixels, not yet supported")
        sys.exit(2)

    # ugly, TextIO seems to be incorrectly treated as if it's not a
    # subclass of TextIOBase by some linters.
    octo = OctoStream(stream)  # type: ignore

    # Make code shorter by tearing off the instance methods and
    # turning them into local funcs. Annoys linters.
    print = octo.print
    comment = octo.comment
    label = octo.label
    pad_for_label = octo.pad_for_label_name
    multi_statement_line = octo.multi_statement_line
    begin_indented_func = octo.begin_indented_func
    end_indented_func = octo.end_indented_func

    compact_glyphtable = True

    kern_px = 1

    draw_char_reg = "v0"
    draw_x_reg = "v1"
    draw_y_reg = "v2"

    width_char_reg = "v0"

    prefix = "smallfont"

    offset = font_data.first_glyph

    # generate label names
    draw_func_name = prefix + "_draw_glyph"
    width_func_name = prefix + "_glyph_width"
    widthtable_name = prefix + "_width_table"
    glyphtable_name = prefix + "_glyph_table"

    # header
    print()
    available_chars = ''.join(chr(i) if i in glyphs else '' for i in range(255))
    print(f"# Font: {prefix}  Available characters: {available_chars}")

    # generate glyph drawing routine
    print()
    comment(f"Call with {draw_char_reg} = ASCII character, {draw_x_reg} = x, {draw_y_reg} = y")
    comment(f"Returns with {draw_x_reg} incremented by the width of the glyph plus {kern_px}")
    comment(f"Clobbers vF, I{'' if draw_char_reg == width_char_reg else ', ' + width_char_reg}")
    comment(f"Must not be called with {draw_char_reg} < {first_glyph} or {draw_char_reg} > {last_glyph}!")

    begin_indented_func(draw_func_name)
    print(f"{draw_char_reg} += {256 - offset}")
    print(f"i := {glyphtable_name}")

    # for i in range(font_y):

    n_shift = int(log(font_height, 2))
    remainder = font_height - int(pow(n_shift, 2))

    if (n_shift * 2 + remainder + 1) >= font_height:
        n_shift = 0
        remainder = font_height

    if n_shift > 0:
        multi_statement_line([f"i += {draw_char_reg}"] * remainder)
        multi_statement_line([f"{draw_char_reg} <<= {draw_char_reg}"] * n_shift)
        print(f"i += {draw_char_reg}")
        multi_statement_line([f"{draw_char_reg} >>= {draw_char_reg}"] * n_shift)

    else:
        multi_statement_line([f"i += {draw_char_reg}"] * remainder)

    print(f"sprite {draw_x_reg} {draw_y_reg} {font_height}")

    if draw_char_reg != width_char_reg:
        print(f"{width_char_reg} := {draw_char_reg}")

    print(f"{width_func_name}_no_offset")
    print(f"{draw_x_reg} += {width_char_reg}")
    print(f"{draw_x_reg} += 1")

    end_indented_func()

    # returns width of a particular glyph
    print()
    comment(f"Call with {width_char_reg} = ASCII character")
    comment(f"Returns {width_char_reg} = width of glyph in pixels")
    comment(f"Clobbers vF, I")
    comment(f"Must not be called with {width_char_reg} < {first_glyph} or {width_char_reg} > {last_glyph}!")

    label(width_func_name)
    octo.indent_level += 1

    # todo check if this is a bug? no return
    print(f"{width_char_reg} += {256 - offset}")
    octo.indent_level -= 1

    begin_indented_func(f"{width_func_name}_no_offset")

    print(f"i := {widthtable_name}")
    print(f"i += {width_char_reg}")
    print(f"load {width_char_reg}")
    end_indented_func()

    # string drawing routine
    label(f"{prefix}draw_str")

    # calculate and output the width table
    for i in range(first_glyph, last_glyph + 1):
        glyph_width = len(glyphs[i]) // font_height
        octo.byte_queue.append(glyph_width)
    octo.write_queued_data_with_label(widthtable_name)

    # calculate and output the glyph data
    for glyph_code in range(first_glyph, last_glyph + 1):
        glyph = glyphs[glyph_code]
        glyph_width, glyph_height = glyph.size
        pixels = bytes(glyph)

        if not compact_glyphtable:
            print()
            pad = pad_for_label(widthtable_name)
            print(f" {pad}# {glyph_code} \'{chr(glyph_code)}\': gl{glyph_code}  {pad}", end='')

        # only supports up to eight right now
        char_size = 8
        for row_start_index in range(0, len(pixels), glyph_width):
            pixels_from_image = pixels[row_start_index:row_start_index + glyph_width]
            packed_row_data = 0

            # use the binary mask to pad the
            for pixel in pixels_from_image:
                packed_row_data = (packed_row_data  << 1) | (1 if pixel else 0)

            # align to the left
            packed_row_data  <<= char_size - glyph_width

            octo.byte_queue.append(packed_row_data)

    octo.write_queued_data_with_label(glyphtable_name)

#    print "# " + font_file + ", " + str(font_points) + " points, height " + str(height) + " px, widest " + str(max_width) + " px"
#    print "# Exporting: " + font_glyphs
#    print

#    for glyph in font_glyphs:
#        print_character(font, glyph, height, alignments)


def main():

    prog, argv = sys.argv[0], sys.argv[1:]

    help = prog + ' <textfont-file>'
    try:
        opts, args = getopt.getopt(argv, "h")
    except getopt.GetoptError:
        print(help)
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print(help)
            sys.exit()
    if len(args) != 1:
        print(help)
        sys.exit(2)

#    input_filename = args[0]

#    if input_filename == '-':
#        infile = std
    #infile = open(input_filename, "r")

    infile = fileinput.input()

    # font_data = parse_textfont_file(infile)
    font_data = TextFontFile(infile)
#    print(file_input)
#    print(file_input.glyphs)
#    return

    emit_octo(sys.stdout, font_data)

if __name__ == "__main__":
   main()
