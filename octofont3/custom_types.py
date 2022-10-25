"""
Custom types used as annotations or building blocks of larger types.

Module members fall into two categories:

    * IO & Streams
    * Image & Font support

IO & Streams heavily lean on Protocols for annotating file-like objects
per Guido van Rossum's advice on the subject:
https://github.com/python/typing/discussions/829#discussioncomment-1150579
"""
from __future__ import annotations
from array import array
from collections import namedtuple
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple, Protocol, Optional, Union, runtime_checkable, Any, TypeVar, Callable, ByteString, Sequence, \
    Mapping, Dict, Iterable, overload, Iterator

from typing_extensions import Self

T = TypeVar('T')
ValidatorFunc = Callable[[Any, ], bool]
SelectorCallable = Union[Callable[[T, ...], T], Callable[[Iterable[T]], T]]

# Partial workaround for there being no way to represent buffer protocol
# support via typing. Relevant PEP: https://peps.python.org/pep-0687/
BytesLike = Union[ByteString, array]

PathLike = Union[Path, str, bytes]
StreamTypeVar = TypeVar('StreamTypeVar')


# Generic stream method Protocols
@runtime_checkable
class HasWrite(Protocol[StreamTypeVar]):
    def write(self, b: StreamTypeVar) -> int:
        ...


@runtime_checkable
class HasRead(Protocol[StreamTypeVar]):
    def read(self, hint: int = -1) -> StreamTypeVar:
        ...


@runtime_checkable
class HasReadline(Protocol[StreamTypeVar]):

    def readline(self) -> StreamTypeVar:
        ...


# Type-specific classes
@runtime_checkable
class HasBytesWrite(Protocol):
    def write(self, b: BytesLike) -> int:
        ...


# Combined path + stream types for resources / loading
PathLikeOrHasRead = Union[HasRead[StreamTypeVar], PathLike]
PathLikeOrHasReadline = Union[HasReadline[StreamTypeVar], PathLike]
PathLikeOrHasWrite = Union[HasWrite[StreamTypeVar], PathLike]
PathLikeOrHasStreamFunc = Union[
    PathLike,
    HasRead[StreamTypeVar],
    HasWrite[StreamTypeVar],
    HasReadline[StreamTypeVar]]


class SequenceLike(Protocol[T]):
    """
    Baseclass for sequence-like Protocols to inherit from.

    It helps define protocols covering both the original sequences and
    classes that imitate sequences without subclassing a sequence type.
    """
    def __iter__(self) -> Iterator[T]:
        ...

    @overload
    def __getitem__(self, item: int) -> T:
        ...

    @overload
    def __getitem__(self, item: slice) -> SequenceLike[T]:
        ...

    def __getitem__(self, item: Union[int, slice]) -> Union[int, SequenceLike[T]]:
        ...

    def __len__(self) -> int:
        ...


@runtime_checkable
class Coord(SequenceLike[int], Protocol):

    def __len__(self) -> int:
        return 2


CoordFancy = namedtuple('CoordFancy', ['x', 'y'])


@runtime_checkable
class Size(SequenceLike[int], Protocol):

    def __len__(self) -> int:
        return 2


SizeFancy = namedtuple('SizeFancy', ['width', 'height'])


@runtime_checkable
class BoundingBox(SequenceLike[int], Protocol):
    """
    Protocol to cover all bounding box behavior.

    It covers the original bounding box tuple behavior, as well as the
    class-based bounding boxes that mimic it.
    """

    def __len__(self) -> int:
        return 4


BboxSimple = Tuple[int, int, int, int]


# Convenience constant for BboxClassABC subclasses
BBOX_PROP_NAMES = ('left', 'top', 'right', 'bottom')


class CompareByLenAndElementsMixin:
    """
    Ease compatibility when comparing against other sequences.
    """

    def __eq__(self: SequenceLike, other: SequenceLike) -> bool:
        len_self = len(self)
        if len(other) != len_self:
            raise ValueError(
                f"Invalid comparison: Bounding boxes must be of value 4, but got {other}")

        for i in range(len_self):
            if self[i] != other[i]:
                return False
        return True


class HashAsTupleMixin:
    """
    Allows classes to be hashed as if they were tuples.

    Requirements for use:

        1. This is placed early enough in the parent class order to
           ensure __hash__ isn't overridden. Putting this class first
           may be easiest.
        2. The parent class will be in an immutable state when it is
           hashed.
        3. The subclass is sufficiently Sequence-like for tuple() to
           convert it.
    """
    def __hash__(self: SequenceLike):
        return hash(tuple(self))


class BboxFancy(HashAsTupleMixin, CompareByLenAndElementsMixin, tuple):

    @overload
    def __new__(cls, left: int, top: int, right: int, bottom: int) -> BboxFancy:
        return cls.__new__(cls, left, top, right, bottom)

    @overload
    def __new__(cls, right: int, bottom: int) -> BboxFancy:
        return cls.__new__(cls, 0, 0, right, bottom)

    @overload
    def __new__(cls, size: Size):
        return cls.__new__(cls, 0, 0, size[0], size[1])

    @overload
    def __new__(cls, sequence: Sequence) -> BboxFancy:
        return cls.__new__(cls, sequence)

    def __new__(cls, *args):

        if len(args) == 1:
            # Unpack a single collection from the arguments
            args = tuple(args[0])

        if len(args) == 2:
            # If args variable is of length 2, treat it as the end position
            args = (0, 0) + tuple(args)

        if len(args) != 4:
            raise ValueError('Must be a sequence of length 4!')

        return super(BboxFancy, cls).__new__(cls, args)

    # *args is included to match __new__'s signature
    # so type checkers behave correctly.
    def __init__(self, *args):
        self._size = SizeFancy(
            self.right - self.left,
            self.bottom - self.top)

    @property
    def size(self) -> Size:
        return self._size

    @property
    def left(self) -> int:
        return self[0]

    @property
    def top(self) -> int:
        return self[1]

    @property
    def right(self) -> int:
        return self[2]

    @property
    def bottom(self) -> int:
        return self[3]

    @property
    def width(self) -> int:
        return self._size.width

    @property
    def height(self) -> int:
        return self._size.height


@runtime_checkable
class ImageCoreLike(Protocol):
    """
    An attempt at typing the Image.core internal class.

    It's unclear if there's a good way to handle this. Using Image.core
    appears to be crucial to interacting with font drawing in pillow,
    but the pillow source also warns that Image.core is not part of
    the public API and may vanish at any time.

    Using Image.core directly does not work with linters because the
    .pyi file for PIL.Image does not provide it. A bad alternative to
    protocols is the following::

        ImageCore = type(Image.new('1', (0, 0), 0).im)

    The protocol approach seems better by comparison.
    """
    mode: str
    size: Size

    def getbbox(self) -> Optional[BoundingBox]:
        """
        Returns None if the core is empty.

        :return:
        """
        ...

    def getpixel(self, position: Sequence) -> Union[int, Tuple[int, ...]]:
        """
        Returns the value for a pixel in the image.

        :param position:
        :return:
        """
        ...

    def __len__(self) -> int:
        ...

    def __bytes__(self) -> bytes:
        ...


@runtime_checkable
class ImageFontLike(Protocol):
    """
    The features required for PIL.ImageDraw to use an object as a font
    """

    def getmask(self, text: str, mode: str = '') -> ImageCoreLike:
        ...

    def getbbox(self, text: str) -> Optional[BoundingBox]:
        ...


GlyphMapping = Mapping[str, ImageCoreLike]
GlyphDict = Dict[str, ImageCoreLike]


@dataclass
class GlyphMetadata:
    """
    Keep track of bounding box information about glyphs.

    Glyphs can have empty actual data despite having a bounding box. In
    this case, bitmap_bbox will be None.

    This class does not store the PIL.Image.core object itself because
    doing so causes issues with dataclass library internals.
    """
    bitmap_bbox: Optional[BboxFancy]
    glyph_bbox: BboxFancy
    bitmap_size: Size
    bitmap_len_bytes: int

    @classmethod
    def from_font_glyph(
        cls,
        bitmap: ImageCoreLike,
        glyph_bbox: BoundingBox
    ) -> "GlyphMetadata":

        # get the stated values
        glyph_bbox = BboxFancy(*glyph_bbox)
        bitmap_bbox = None

        if bitmap is not None:
            bitmap_bbox = bitmap.getbbox()
            if bitmap_bbox is not None:
                bitmap_bbox = BboxFancy(*bitmap_bbox)

        return cls(
            glyph_bbox=glyph_bbox,
            bitmap_bbox=bitmap_bbox,
            bitmap_size=SizeFancy(*bitmap.size),
            bitmap_len_bytes=len(bitmap)
        )


class MissingGlyphError(Exception):
    """
    1 or more required glyphs were not found.

    Does not subclass Key or Index errors because the underlying
    representation below may be either.
    """
    def __init__(self, message_header, missing_glyph_codes: Sequence[int]):
        super().__init__(f"{message_header} : {missing_glyph_codes}")
        self.missing_glyph_codes = missing_glyph_codes

    @classmethod
    def default_msg(cls, missing_glyph_codes: Sequence[int]):
        cls(
            "One or more required glyphs was found to be missing",
            missing_glyph_codes)
