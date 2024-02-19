import logging
from io import IOBase
from pathlib import PurePath
from typing import Optional, Union

from pdfminer.high_level import extract_pages
from pdfminer.layout import LAParams

from hotpdf.encodings.encoder import EncodingType
from hotpdf.memory_map import MemoryMap

logging.getLogger("pdfminer").setLevel(logging.ERROR)


def __make_custom_laparams_object(
    laparams: Optional[dict[str, Union[float, bool]]] = None,
) -> LAParams:
    laparams_obj = LAParams()
    if not laparams:
        return laparams_obj
    for key in laparams:
        if hasattr(laparams_obj, key):
            laparams_obj.__setattr__(key, laparams[key])
    return laparams_obj


def __process(
    source: Union[PurePath, str, IOBase],
    password: str = "",
    page_numbers: Optional[list[int]] = None,
    laparams: Optional[dict[str, Union[float, bool]]] = None,
    include_annotation_spaces: bool = False,
    cid_overwrite_charset: Optional[EncodingType] = None,
) -> list[MemoryMap]:
    pages: list[MemoryMap] = []
    page_numbers = sorted(page_numbers) if page_numbers else []

    laparams_obj = __make_custom_laparams_object(laparams)

    hl_page_layouts = extract_pages(
        source, password=password, page_numbers=page_numbers, caching=False, laparams=laparams_obj
    )
    for page_layout in hl_page_layouts:
        parsed_page: MemoryMap = MemoryMap()
        parsed_page.build_memory_map()
        parsed_page.load_memory_map(
            page=page_layout,
            include_annotation_spaces=include_annotation_spaces,
            cid_overwrite_charset=cid_overwrite_charset,
        )
        pages.append(parsed_page)
    return pages


def process(
    source: Union[PurePath, str, IOBase],
    password: str = "",
    page_numbers: Optional[list[int]] = None,
    laparams: Optional[dict[str, Union[float, bool]]] = None,
    include_annotation_spaces: bool = False,
    cid_overwrite_charset: Optional[EncodingType] = None,
) -> list[MemoryMap]:
    return __process(
        source=source,
        password=password,
        page_numbers=page_numbers,
        laparams=laparams,
        include_annotation_spaces=include_annotation_spaces,
        cid_overwrite_charset=cid_overwrite_charset,
    )
