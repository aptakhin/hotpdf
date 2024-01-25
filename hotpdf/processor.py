import html
import logging
import os
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from enum import Enum
from pathlib import Path
from typing import Union

from hotpdf.helpers import nanoid
from hotpdf.memory_map import MemoryMap


class Result(Enum):
    LOADED = 0
    LOCKED = 1
    WRONG_PASSWORD = 2
    UNKNOWN_ERROR = 3


def process(
    source: Union[str, bytes], password: str, drop_duplicate_spans: bool, first_page: int, last_page: int
) -> list[MemoryMap]:
    xml_file = __generate_xml_file(source, password, first_page, last_page)
    pages = __parse_xml(xml_file, drop_duplicate_spans)
    return pages


def __generate_xml_file(source: Union[str, bytes], password: str, first_page: int, last_page: int) -> Path:
    """Generate XML notation of PDF File.

    Args:
        file_path (str): The path to the PDF file.
        password (str): The password to use to unlock the file
        first_page (int): The first page to extract.
        last_page (int): The last page to extract.
    Raises:
        PermissionError: If the password is missing or wrong.
        RuntimeError: If ghostscripts generates an unknown error.
    Returns:
        str: XML File Path.
    """
    temp_xml_file_path = Path(tempfile.gettempdir(), nanoid.generate_nano_id() + ".xml")
    result = __call_ghostscript(source, temp_xml_file_path, password, first_page, last_page)
    __handle_gs_result(result)
    return __clean_xml(temp_xml_file_path)


def __call_ghostscript(
    source: Union[str, bytes], temp_xml_file_path: Path, password: str, first_page: int, last_page: int
) -> Result:
    ghostscript = "gs" if os.name != "nt" else "gswin64c"
    command_line_args = [ghostscript, "-dNOPAUSE", "-dBATCH", "-dSAFER", "-dTextFormat=1", "-sDEVICE=txtwrite"]

    if password:
        command_line_args.append(f'-sPDFPassword="{password}"')
    if first_page:
        command_line_args.append(f"-dFirstPage={first_page}")
    if last_page:
        command_line_args.append(f"-dLastPage={last_page}")

    command_line_args.append(f'-sOutputFile="{temp_xml_file_path}"')

    # Uses gs in pipe mode
    pipe = type(source) is bytes
    command_line_args.append("-" if pipe else str(source))

    gs_call = " ".join(command_line_args)

    output = subprocess.run(gs_call, shell=ghostscript == "gs", input=source if pipe else None, capture_output=True)
    status = __validate_gs_output(output)

    return status


def __clean_xml(temporary_xml_path: Path) -> Path:
    """
    Clean the raw xlm file generated by ghostscript.
    Apply changes directly to the temporaryfile.

    Args:
        temporary_xml_file_name (str): the temporary file outputted by ghostscript
    """
    with open(temporary_xml_path, "r+", encoding="utf-8") as f:
        raw_xml = f.read()
        raw_xml = re.sub(r"(&#x[0-9]+;)", "", raw_xml)
        raw_xml = re.sub(r"(&quot;)", "'", raw_xml)
        raw_xml = html.unescape(raw_xml)
        raw_xml = re.sub(
            r"[\x00-\x08\x0b\x0c\x0e-\x1F\uD800-\uDFFF\uFFFE\uFFFF]", "", raw_xml
        )  # Remove invalid XML chars
        raw_xml = raw_xml.replace("&", "&amp;")
        raw_xml = re.sub(r"<(?!/?[a-zA-Z])", "&lt;", raw_xml)
        raw_xml = '<?xml version="1.0" encoding="UTF-8"?><pages>' + raw_xml + "</pages>"
        f.seek(0)
        f.write(raw_xml)
        f.truncate()
    return temporary_xml_path


def __validate_gs_output(output: subprocess.CompletedProcess[bytes]) -> Result:
    err = output.stderr.decode(errors="ignore") + output.stdout.decode(errors="ignore")
    logging.debug(err)
    if "This file requires a password for access" in err:
        return Result.LOCKED
    if "Password did not work" in err:
        return Result.WRONG_PASSWORD
    if "Unrecoverable error" in err or output.returncode:
        return Result.UNKNOWN_ERROR
    return Result.LOADED


def __handle_gs_result(status: Result) -> None:
    if status == Result.LOADED:
        logging.info("GS: PARSING COMPLETE")
        return

    if status == Result.WRONG_PASSWORD:
        logging.error("GS: WRONG PASSWORD")
        raise PermissionError("Wrong password")

    if status == Result.LOCKED:
        logging.error("GS: FILE IS ENCRYPTED. PROVIDE A PASSWORD")
        raise PermissionError("File is encrypted. You need a password")

    if status == Result.UNKNOWN_ERROR:
        logging.error("GS: UNKNOWN ERROR")
        raise RuntimeError("Unknown error in processing")


def __parse_xml(xml_file_path: Path, drop_duplicate_spans: bool) -> list[MemoryMap]:
    pages: list[MemoryMap] = []
    tree_iterator = ET.iterparse(xml_file_path, events=("start", "end"))
    event: str
    root: ET.Element
    event, root = next(tree_iterator)
    element: ET.Element
    for event, element in tree_iterator:
        if event == "end" and element.tag == "page":
            parsed_page: MemoryMap = MemoryMap()
            parsed_page.build_memory_map()
            parsed_page.load_memory_map(page=element, drop_duplicate_spans=drop_duplicate_spans)
            pages.append(parsed_page)
            element.clear()
        root.clear()
    os.remove(xml_file_path)
    return pages
