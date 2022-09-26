#!/usr/bin/python3
import fileinput
import sys
import getopt

from octofont3.formats.loader import load_font

from octofont3.octo import emit_octo
from octofont3.utils import generate_glyph_sequence


def main():

    prog, argv = sys.argv[0], sys.argv[1:]

    size_points = 8
    glyph_sequence = None

    help = prog + '[-p <point-size>] [-g <glyph-sequence>] <font-file>'
    try:
        opts, args = getopt.getopt(argv, "h:p:g:")
    except getopt.GetoptError:
        print(help)
        sys.exit(2)

    for opt, arg in opts:
        if opt == '-h':
            print(help)
            sys.exit()
        elif opt == '-p':
            size_points = int(arg)
        elif opt == '-g':
            glyph_sequence = arg

    if len(args) != 1:
        print(help)
        sys.exit(2)

    input_filename = args[0]

#    if input_filename == '-':
#        infile = std

    # infile = fileinput.input()

    font = load_font(input_filename, size_points)
    emit_octo(sys.stdout, font, glyph_sequence=glyph_sequence)

if __name__ == "__main__":
   main()