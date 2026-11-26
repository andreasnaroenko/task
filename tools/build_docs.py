"""Генерация документов проекта: инструкции, отчёта и презентации.

Скрипт вспомогательный и не входит в само приложение. Для его работы
требуются пакеты python-docx, python-pptx и Pillow (только на этапе
подготовки документов, не для запуска СУБД).

Запуск:
    python tools/build_docs.py
"""

from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor as PptRGB
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt as PptPt

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

# ----------------------------------------------------------------------
# Общие настройки DOCX
# ----------------------------------------------------------------------
FONT = "Times New Roman"
CODE_FONT = "Consolas"
ACCENT = RGBColor(0x1F, 0x4E, 0x79)
GREY = RGBColor(0x59, 0x59, 0x59)


def _set_run_font(run, name: str = FONT, size: int | None = None,
                  bold: bool | None = None, italic: bool | None = None,
                  color: RGBColor | None = None) -> None:
    run.font.name = name
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    if italic is not None:
        run.font.italic = italic
    if color is not None:
        run.font.color.rgb = color
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:ascii"), name)
    rfonts.set(qn("w:hAnsi"), name)
    rfonts.set(qn("w:eastAsia"), name)
    rfonts.set(qn("w:cs"), name)


def _set_style_font(style, name: str, size: int, bold: bool | None = None) -> None:
    style.font.name = name
    style.font.size = Pt(size)
    if bold is not None:
        style.font.bold = bold
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:ascii"), name)
    rfonts.set(qn("w:hAnsi"), name)
    rfonts.set(qn("w:eastAsia"), name)
    rfonts.set(qn("w:cs"), name)


def _configure_document(doc: Document, gost: bool = True, landscape: bool = False) -> None:
    section = doc.sections[0]
    if landscape:
        section.orientation = WD_ORIENT.LANDSCAPE
        section.page_width = Cm(29.7)
        section.page_height = Cm(21)
        section.left_margin = Cm(2)
        section.right_margin = Cm(1.5)
        section.top_margin = Cm(1.5)
        section.bottom_margin = Cm(1.5)
    else:
        section.left_margin = Cm(3)
        section.right_margin = Cm(1.5)
        section.top_margin = Cm(2)
        section.bottom_margin = Cm(2)

    normal = doc.styles["Normal"]
    _set_style_font(normal, FONT, 14)
    normal.paragraph_format.line_spacing = 1.5
    normal.paragraph_format.space_after = Pt(0)
    normal.paragraph_format.first_line_indent = Cm(1.25)
    normal.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    for level, size in ((1, 16), (2, 14), (3, 14)):
        style = doc.styles[f"Heading {level}"]
        _set_style_font(style, FONT, size, bold=True)
        style.font.color.rgb = RGBColor(0, 0, 0)
        style.paragraph_format.line_spacing = 1.5
        style.paragraph_format.space_before = Pt(12 if level > 1 else 0)
        style.paragraph_format.space_after = Pt(6)
        style.paragraph_format.first_line_indent = Cm(0)
        if level == 1:
            style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
        else:
            style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
            style.paragraph_format.first_line_indent = Cm(1.25)

    # Нумерация страниц: титульный лист без номера.
    section.different_first_page_header_footer = True
    footer = section.footer
    paragraph = footer.paragraphs[0]
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _add_page_field(paragraph)

    settings = doc.settings.element
    update = OxmlElement("w:updateFields")
    update.set(qn("w:val"), "true")
    settings.append(update)


def _add_page_field(paragraph) -> None:
    run = paragraph.add_run()
    _set_run_font(run, FONT, 12)
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = " PAGE "
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    text = OxmlElement("w:t")
    text.text = "2"
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    for element in (begin, instr, separate, text, end):
        run._r.append(element)


def _add_toc(doc: Document) -> None:
    # Компактные стили оглавления, чтобы оно гарантированно уместилось
    # на одной странице и не создавало пустую страницу.
    for level in (1, 2, 3):
        name = f"TOC {level}"
        try:
            style = doc.styles[name]
        except KeyError:
            style = doc.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
        style.base_style = doc.styles["Normal"]
        _set_style_font(style, FONT, 13, bold=(level == 1))
        style.paragraph_format.line_spacing = 1.0
        style.paragraph_format.space_after = Pt(2)
        style.paragraph_format.space_before = Pt(0)
        style.paragraph_format.first_line_indent = Cm(0)
        if level > 1:
            style.paragraph_format.left_indent = Cm(0.6 * (level - 1))

    heading = doc.add_paragraph()
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
    heading.paragraph_format.first_line_indent = Cm(0)
    heading.paragraph_format.page_break_before = True
    run = heading.add_run("СОДЕРЖАНИЕ")
    _set_run_font(run, FONT, 16, bold=True)

    paragraph = doc.add_paragraph()
    paragraph.paragraph_format.first_line_indent = Cm(0)
    run = paragraph.add_run()
    _set_run_font(run, FONT, 14)
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = r' TOC \o "1-3" \h \z \u '
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    placeholder = OxmlElement("w:t")
    placeholder.text = "Обновите оглавление: выделите его и нажмите F9."
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    for element in (begin, instr, separate, placeholder, end):
        run._r.append(element)


def _add_title_page_report(doc: Document) -> None:
    def line(text: str, size: int = 14, bold: bool = False, space_after: int = 0,
             align=WD_ALIGN_PARAGRAPH.CENTER) -> None:
        paragraph = doc.add_paragraph()
        paragraph.alignment = align
        paragraph.paragraph_format.first_line_indent = Cm(0)
        paragraph.paragraph_format.line_spacing = 1.0
        paragraph.paragraph_format.space_after = Pt(space_after)
        run = paragraph.add_run(text)
        _set_run_font(run, FONT, size, bold=bold)

    line("ДЕПАРТАМЕНТ ОБРАЗОВАНИЯ ТОМСКОЙ ОБЛАСТИ", 12)
    line("ОБЛАСТНОЕ ГОСУДАРСТВЕННОЕ БЮДЖЕТНОЕ", 12)
    line("ПРОФЕССИОНАЛЬНОЕ ОБРАЗОВАТЕЛЬНОЕ УЧРЕЖДЕНИЕ", 12)
    line("«ТОМСКИЙ ТЕХНИКУМ ИНФОРМАЦИОННЫХ ТЕХНОЛОГИЙ»", 12, space_after=18)
    line("Специальность 09.02.07", 13)
    line("«Информационные системы и программирование»", 13, space_after=48)
    line("ОТЧЁТ", 24, bold=True, space_after=6)
    line("по учебной практике", 16)
    line("Командная разработка приложения", 16, space_after=24)
    line("Тема: разработка системы управления базами данных", 14)
    line("«РЕЕСТР» с GUI-терминалом", 14, bold=True, space_after=60)

    for text in (
        "Выполнили: студенты группы ____________",
        "__________________ /____________________/",
        "",
        "Руководитель: ____________________________",
        "__________________ /____________________/",
    ):
        line(text, 13, align=WD_ALIGN_PARAGRAPH.RIGHT)

    for _ in range(6):
        line("", 12)
    line("Томск 2026", 13)


def _add_title_page_manual(doc: Document) -> None:
    def line(text: str, size: int = 14, bold: bool = False, space_after: int = 0):
        paragraph = doc.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.paragraph_format.first_line_indent = Cm(0)
        paragraph.paragraph_format.line_spacing = 1.0
        paragraph.paragraph_format.space_after = Pt(space_after)
        run = paragraph.add_run(text)
        _set_run_font(run, FONT, size, bold=bold)

    for _ in range(4):
        line("", 12)
    line("ИНСТРУКЦИЯ ПОЛЬЗОВАТЕЛЯ", 26, bold=True, space_after=20)
    line("Приложение «РЕЕСТР»", 20, space_after=8)
    line("Учебная система управления базами данных", 16)
    line("с GUI-терминалом", 16, space_after=16)
    line("Версия 1.0", 14)
    for _ in range(8):
        line("", 12)
    line("Томск 2026", 13)
    doc.add_page_break()


# ----------------------------------------------------------------------
# Markdown -> DOCX
# ----------------------------------------------------------------------
INLINE_RE = re.compile(r"(\*\*.+?\*\*|`[^`]+`|\*[^*]+\*)")


def _add_inline(paragraph, text: str, base_size: int = 14) -> None:
    for part in INLINE_RE.split(text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            run = paragraph.add_run(part[2:-2])
            _set_run_font(run, FONT, base_size, bold=True)
        elif part.startswith("`") and part.endswith("`"):
            run = paragraph.add_run(part[1:-1])
            _set_run_font(run, CODE_FONT, base_size - 1, color=ACCENT)
        elif part.startswith("*") and part.endswith("*") and len(part) > 2:
            run = paragraph.add_run(part[1:-1])
            _set_run_font(run, FONT, base_size, italic=True)
        else:
            run = paragraph.add_run(part)
            _set_run_font(run, FONT, base_size)


def _shade_paragraph(paragraph, fill: str) -> None:
    ppr = paragraph._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    ppr.append(shd)


def _add_code_block(doc: Document, lines: list[str]) -> None:
    paragraph = doc.add_paragraph()
    paragraph.paragraph_format.first_line_indent = Cm(0)
    paragraph.paragraph_format.left_indent = Cm(0.5)
    paragraph.paragraph_format.line_spacing = 1.0
    paragraph.paragraph_format.space_before = Pt(6)
    paragraph.paragraph_format.space_after = Pt(6)
    paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
    _shade_paragraph(paragraph, "F2F2F2")
    run = paragraph.add_run("\n".join(lines))
    _set_run_font(run, CODE_FONT, 9)


def _add_cell_text(cell, text: str, bold: bool = False, size: int = 11) -> None:
    paragraph = cell.paragraphs[0]
    paragraph.paragraph_format.first_line_indent = Cm(0)
    paragraph.paragraph_format.line_spacing = 1.0
    paragraph.paragraph_format.space_after = Pt(0)
    paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
    if bold:
        run = paragraph.add_run(text)
        _set_run_font(run, FONT, size, bold=True)
    else:
        _add_inline(paragraph, text, size)


def _add_markdown_table(doc: Document, rows: list[list[str]]) -> None:
    if not rows:
        return
    columns = max(len(row) for row in rows)
    table = doc.add_table(rows=len(rows), cols=columns)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = True

    for row_index, row in enumerate(rows):
        for column_index in range(columns):
            text = row[column_index] if column_index < len(row) else ""
            cell = table.cell(row_index, column_index)
            _add_cell_text(cell, text, bold=(row_index == 0))
            if row_index == 0:
                shading = OxmlElement("w:shd")
                shading.set(qn("w:val"), "clear")
                shading.set(qn("w:color"), "auto")
                shading.set(qn("w:fill"), "D9E2F3")
                cell._tc.get_or_add_tcPr().append(shading)
                tr_pr = table.rows[0]._tr.get_or_add_trPr()
                header = OxmlElement("w:tblHeader")
                header.set(qn("w:val"), "true")
                tr_pr.append(header)

    # Небольшие таблицы не разрываем между страницами.
    if len(rows) <= 8:
        for row_index, row in enumerate(table.rows):
            tr_pr = row._tr.get_or_add_trPr()
            cant_split = OxmlElement("w:cantSplit")
            cant_split.set(qn("w:val"), "true")
            tr_pr.append(cant_split)
            if row_index < len(table.rows) - 1:
                for cell in row.cells:
                    for paragraph in cell.paragraphs:
                        paragraph.paragraph_format.keep_with_next = True

    paragraph = doc.add_paragraph()
    paragraph.paragraph_format.space_after = Pt(6)
    paragraph.paragraph_format.first_line_indent = Cm(0)
    run = paragraph.add_run("")
    _set_run_font(run, FONT, 6)


def _add_image(doc: Document, src: Path, caption: str, width_cm: float = 16.0) -> None:
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.first_line_indent = Cm(0)
    paragraph.paragraph_format.space_before = Pt(6)
    paragraph.paragraph_format.space_after = Pt(3)
    paragraph.paragraph_format.keep_with_next = True
    run = paragraph.add_run()
    run.add_picture(str(src), width=Cm(width_cm))

    if caption:
        cap = doc.add_paragraph()
        cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cap.paragraph_format.first_line_indent = Cm(0)
        cap.paragraph_format.space_after = Pt(10)
        run = cap.add_run(caption)
        _set_run_font(run, FONT, 12, italic=True, color=GREY)


def _is_separator_row(cells: list[str]) -> bool:
    return bool(cells) and all(re.fullmatch(r":?-{2,}:?", cell.strip()) for cell in cells)


def markdown_to_docx(
    md_path: Path,
    out_path: Path,
    *,
    gost: bool = True,
    report_title: bool = False,
    manual_title: bool = False,
    skip_to_heading: str | None = None,
    image_width: float = 16.0,
    landscape: bool = False,
) -> None:
    doc = Document()
    _configure_document(doc, gost=gost, landscape=landscape)
    doc.core_properties.title = md_path.stem
    doc.core_properties.author = "Команда проекта «РЕЕСТР»"

    if report_title:
        _add_title_page_report(doc)
        _add_toc(doc)
    if manual_title:
        _add_title_page_manual(doc)

    lines = md_path.read_text(encoding="utf-8").splitlines()
    if skip_to_heading:
        for index, line in enumerate(lines):
            if line.strip() == skip_to_heading:
                lines = lines[index:]
                break

    in_code = False
    code_lines: list[str] = []
    first_block = True
    index = 0
    paragraph_lines: list[str] = []

    def flush_paragraph() -> None:
        nonlocal first_block
        if not paragraph_lines:
            return
        text = " ".join(part.strip() for part in paragraph_lines).strip()
        paragraph_lines.clear()
        paragraph = doc.add_paragraph()
        _add_inline(paragraph, text)
        first_block = False

    while index < len(lines):
        raw = lines[index]
        stripped = raw.strip()

        if stripped.startswith("```"):
            flush_paragraph()
            if in_code:
                _add_code_block(doc, code_lines)
                code_lines = []
                in_code = False
            else:
                in_code = True
            index += 1
            continue
        if in_code:
            code_lines.append(raw)
            index += 1
            continue

        if not stripped:
            flush_paragraph()
            index += 1
            continue

        if stripped == "---":
            flush_paragraph()
            paragraph = doc.add_paragraph()
            paragraph.paragraph_format.space_after = Pt(6)
            paragraph.paragraph_format.first_line_indent = Cm(0)
            index += 1
            continue

        if stripped.startswith("!["):
            flush_paragraph()
            match = re.match(r"!\[(.*?)\]\((.*?)\)", stripped)
            if match:
                caption, rel = match.groups()
                _add_image(doc, DOCS / rel, caption, width_cm=image_width)
            index += 1
            continue

        if stripped.startswith("#"):
            flush_paragraph()
            level = len(stripped) - len(stripped.lstrip("#"))
            text = stripped[level:].strip()
            if level == 1 and gost:
                text = text.upper()
            paragraph = doc.add_heading(level=min(level, 3))
            if level == 1 and not first_block:
                paragraph.paragraph_format.page_break_before = True
            run = paragraph.add_run(text)
            size = {1: 16, 2: 14, 3: 14}.get(level, 14)
            _set_run_font(run, FONT, size, bold=True)
            first_block = False
            index += 1
            continue

        if stripped.startswith(">"):
            flush_paragraph()
            quote_lines: list[str] = []
            while index < len(lines) and lines[index].strip().startswith(">"):
                quote_lines.append(lines[index].strip()[1:].strip())
                index += 1
            paragraph = doc.add_paragraph()
            paragraph.paragraph_format.left_indent = Cm(1)
            paragraph.paragraph_format.first_line_indent = Cm(0)
            _add_inline(paragraph, " ".join(quote_lines))
            for run in paragraph.runs:
                run.font.italic = True
                run.font.color.rgb = GREY
            first_block = False
            continue

        if stripped.startswith("|") and stripped.endswith("|"):
            flush_paragraph()
            table_rows: list[list[str]] = []
            while index < len(lines):
                candidate = lines[index].strip()
                if not (candidate.startswith("|") and candidate.endswith("|")):
                    break
                cells = [cell.strip() for cell in candidate.strip("|").split("|")]
                if not _is_separator_row(cells):
                    table_rows.append(cells)
                index += 1
            _add_markdown_table(doc, table_rows)
            first_block = False
            continue

        if re.match(r"^[*-]\s+", stripped):
            flush_paragraph()
            text = re.sub(r"^[*-]\s+", "", stripped)
            paragraph = doc.add_paragraph(style="List Bullet")
            paragraph.paragraph_format.first_line_indent = Cm(0)
            paragraph.paragraph_format.line_spacing = 1.5
            _add_inline(paragraph, text)
            first_block = False
            index += 1
            continue

        if re.match(r"^\d+\.\s+", stripped):
            flush_paragraph()
            text = re.sub(r"^\d+\.\s+", "", stripped)
            paragraph = doc.add_paragraph(style="List Number")
            paragraph.paragraph_format.first_line_indent = Cm(0)
            paragraph.paragraph_format.line_spacing = 1.5
            _add_inline(paragraph, text)
            first_block = False
            index += 1
            continue

        paragraph_lines.append(stripped)
        index += 1

    flush_paragraph()
    if in_code and code_lines:
        _add_code_block(doc, code_lines)

    doc.save(str(out_path))
    print("saved", out_path)


# ----------------------------------------------------------------------
# Презентация
# ----------------------------------------------------------------------
PBG = PptRGB(0x07, 0x0D, 0x19)
PPANEL = PptRGB(0x0D, 0x17, 0x29)
PACCENT = PptRGB(0x38, 0xBD, 0xF8)
PTEXT = PptRGB(0xDB, 0xE7, 0xF5)
PMUTED = PptRGB(0x7F, 0x95, 0xB3)
PGREEN = PptRGB(0x86, 0xEF, 0xAC)
PYELLOW = PptRGB(0xFC, 0xD3, 0x4D)


def _ppt_bg(slide) -> None:
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = PBG


def _ppt_text(slide, left, top, width, height, text, size=20, color=PTEXT,
              bold=False, align=PP_ALIGN.LEFT, font="Segoe UI"):
    box = slide.shapes.add_textbox(left, top, width, height)
    frame = box.text_frame
    frame.word_wrap = True
    paragraph = frame.paragraphs[0]
    paragraph.alignment = align
    run = paragraph.add_run()
    run.text = text
    run.font.size = PptPt(size)
    run.font.color.rgb = color
    run.font.bold = bold
    run.font.name = font
    return box


def _ppt_title(slide, index: int, title: str, subtitle: str | None = None) -> None:
    _ppt_text(slide, Inches(0.7), Inches(0.35), Inches(9.5), Inches(0.7),
              title, 30, PTEXT, bold=True)
    line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.72),
                                  Inches(1.08), Inches(1.6), Inches(0.05))
    line.fill.solid()
    line.fill.fore_color.rgb = PACCENT
    line.line.fill.background()
    if subtitle:
        _ppt_text(slide, Inches(0.72), Inches(1.16), Inches(11.5), Inches(0.4),
                  subtitle, 13, PMUTED)
    _ppt_text(slide, Inches(0.72), Inches(7.12), Inches(6), Inches(0.25),
              "РЕЕСТР · учебная СУБД с GUI-терминалом", 9, PMUTED)
    _ppt_text(slide, Inches(12.3), Inches(7.12), Inches(0.6), Inches(0.25),
              str(index), 9, PMUTED, align=PP_ALIGN.RIGHT)


def _ppt_bullets(slide, items, left, top, width, height, size=19,
                 color=PTEXT, spacing=10) -> None:
    box = slide.shapes.add_textbox(left, top, width, height)
    frame = box.text_frame
    frame.word_wrap = True
    for index, item in enumerate(items):
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        paragraph.space_after = PptPt(spacing)
        prefix = ""
        if isinstance(item, tuple):
            text, level = item
            prefix = "•  " if level == 0 else "      –  "
            if level == 0:
                paragraph.space_before = PptPt(4)
        else:
            text = item
            prefix = "•  "
        run = paragraph.add_run()
        run.text = prefix + text
        run.font.size = PptPt(size if not isinstance(item, tuple) or item[1] == 0 else size - 3)
        run.font.color.rgb = color if not isinstance(item, tuple) or item[1] == 0 else PMUTED
        run.font.name = "Segoe UI"


def _ppt_image(slide, path: Path, left, top, max_width, max_height) -> None:
    width, height = Image.open(path).size
    scale = min(max_width / width, max_height / height)
    slide.shapes.add_picture(
        str(path), left, top, width=int(width * scale), height=int(height * scale)
    )


def _ppt_table(slide, rows, left, top, width, height) -> None:
    table = slide.shapes.add_table(
        len(rows), len(rows[0]), left, top, width, height
    ).table
    for row_index, row in enumerate(rows):
        for column_index, value in enumerate(row):
            cell = table.cell(row_index, column_index)
            cell.text = ""
            paragraph = cell.text_frame.paragraphs[0]
            run = paragraph.add_run()
            run.text = value
            run.font.size = PptPt(14)
            run.font.name = "Segoe UI"
            run.font.bold = row_index == 0
            run.font.color.rgb = PTEXT
            cell.fill.solid()
            cell.fill.fore_color.rgb = PPANEL if row_index else PptRGB(0x17, 0x2A, 0x45)


def build_presentation(out_path: Path) -> None:
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]

    def new_slide(title, subtitle=None):
        slide = prs.slides.add_slide(blank)
        _ppt_bg(slide)
        _ppt_title(slide, len(prs.slides), title, subtitle)
        return slide

    # 1. Титульный
    slide = prs.slides.add_slide(blank)
    _ppt_bg(slide)
    _ppt_text(slide, Inches(0.9), Inches(1.25), Inches(6.6), Inches(1.1),
              "РЕЕСТР", 54, PACCENT, bold=True)
    _ppt_text(slide, Inches(0.95), Inches(2.35), Inches(6.2), Inches(1.0),
              "учебная СУБД\nс GUI-терминалом", 28, PTEXT, bold=True)
    _ppt_text(slide, Inches(0.95), Inches(4.05), Inches(6.4), Inches(1.2),
              "Командная разработка приложения\nУчебная практика · 09.02.07",
              16, PMUTED)
    _ppt_text(slide, Inches(0.95), Inches(6.25), Inches(6.0), Inches(0.5),
              "Томск · 2026", 14, PMUTED)
    _ppt_image(slide, DOCS / "screenshot_main.png", Inches(7.0), Inches(1.25),
               Inches(5.6), Inches(4.6))
    _ppt_text(slide, Inches(7.0), Inches(6.05), Inches(5.6), Inches(0.5),
              "Данные только в RAM · без сторонних библиотек", 12, PMUTED,
              align=PP_ALIGN.CENTER)

    # 2. Проблема
    slide = new_slide("Задача заказчика", "Государственное ведомство · внутренние реестры")
    _ppt_bullets(slide, [
        "Много реестров и справочников, которые ведутся вручную",
        "Нельзя развернуть полноценную СУБД: требования информационной безопасности",
        "Запрещено стороннее программное обеспечение",
        "Нужна простая система для внутреннего использования",
        "Данные должны храниться только в оперативной памяти",
    ], Inches(0.8), Inches(1.9), Inches(11.8), Inches(4.6), 21)

    # 3. Цель
    slide = new_slide("Цель и задачи проекта", "Что требовалось сделать")
    _ppt_bullets(slide, [
        "Цель: разработать учебную СУБД «РЕЕСТР» с GUI-терминалом",
        "Спроектировать модель данных и командный язык",
        "Реализовать базы данных, таблицы, поля и записи",
        "Добавить проверку типов и обработку ошибок с подсказками",
        "Разработать интерактивный урок по всем возможностям",
        "Подготовить тесты, инструкцию, отчёт и презентацию",
    ], Inches(0.8), Inches(1.9), Inches(11.8), Inches(4.8), 20)

    # 4. Возможности
    slide = new_slide("Что умеет система", "Полный цикл работы с табличными данными")
    _ppt_bullets(slide, [
        "Базы данных: создание, список, выбор, удаление",
        "Таблицы: создание, структура, добавление и удаление полей",
        "Записи: INSERT, SELECT, UPDATE, DELETE по id",
        "Типы: string, int, float, bool с проверкой значений",
        "Ошибки: дубликаты, несуществующие объекты, неверные типы",
        "Обучение: урок из 13 шагов с автоподстановкой команд",
        "Демо-база registry для быстрого показа",
    ], Inches(0.8), Inches(1.9), Inches(11.8), Inches(4.9), 19, spacing=6)

    # 5. Архитектура
    slide = new_slide("Архитектура", "Разделение модели, логики и интерфейса")
    boxes = [
        ("TerminalGUI · tkinter", 0.9, 1.75, 5.3, "ввод команд, вывод, цвета, история"),
        ("Engine · диспетчер", 0.9, 2.95, 5.3, "разбор, вызовы, обработка ошибок"),
        ("DatabaseManager → Database → Table → Field", 0.9, 4.15, 6.7, "хранение данных в RAM"),
    ]
    for text, left, top, width, subtitle in boxes:
        shape = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top),
            Inches(width), Inches(0.9)
        )
        shape.fill.solid()
        shape.fill.fore_color.rgb = PPANEL
        shape.line.color.rgb = PACCENT
        shape.line.width = PptPt(1)
        frame = shape.text_frame
        frame.text = text + "\n" + subtitle
        frame.paragraphs[0].font.size = PptPt(17)
        frame.paragraphs[0].font.bold = True
        frame.paragraphs[0].font.color.rgb = PTEXT
        frame.paragraphs[0].font.name = "Segoe UI"
        if len(frame.paragraphs) > 1:
            frame.paragraphs[1].font.size = PptPt(11)
            frame.paragraphs[1].font.color.rgb = PMUTED
            frame.paragraphs[1].font.name = "Segoe UI"

    for top in (2.65, 3.85):
        connector = slide.shapes.add_connector(
            MSO_CONNECTOR.STRAIGHT, Inches(3.5), Inches(top),
            Inches(3.5), Inches(top + 0.3)
        )
        connector.line.color.rgb = PACCENT

    _ppt_bullets(slide, [
        "Модель не зависит от GUI — тестируется отдельно",
        "Собственный парсер учитывает кавычки и скобки",
        "CommandResult передаёт готовые строки интерфейсу",
    ], Inches(7.95), Inches(1.85), Inches(4.6), Inches(3.2), 15, spacing=10)
    _ppt_text(slide, Inches(7.95), Inches(4.7), Inches(4.6), Inches(0.8),
              "42 автоматических теста\n0 ошибок", 22, PGREEN, bold=True)

    # 6. GUI
    slide = new_slide("GUI-терминал", "Понятный интерфейс и быстрый ввод")
    _ppt_image(slide, DOCS / "screenshot_main.png", Inches(0.65), Inches(1.6),
               Inches(8.1), Inches(5.3))
    _ppt_bullets(slide, [
        "Тёмная тема, крупный моноширинный шрифт",
        "Цветовые статусы: успех, ошибка, подсказка",
        "История ↑ ↓ и автодополнение Tab",
        "Кнопки обучения, справки и демо",
        "Строка состояния: база, таблицы, записи",
    ], Inches(9.0), Inches(1.85), Inches(3.8), Inches(4.4), 14, spacing=10)

    # 7. Данные
    slide = new_slide("Работа с данными", "Структура таблицы, UPDATE и SELECT по id")
    _ppt_image(slide, DOCS / "screenshot_data.png", Inches(0.65), Inches(1.6),
               Inches(8.2), Inches(5.3))
    _ppt_bullets(slide, [
        "DESCRIBE показывает поля и типы",
        "UPDATE меняет только указанные поля",
        "WHERE id = N обязателен",
        "SELECT выводит таблицу с границами",
        "id создаётся автоматически",
    ], Inches(9.1), Inches(1.85), Inches(3.7), Inches(4.4), 14, spacing=10)

    # 8. Ошибки
    slide = new_slide("Валидация и обработка ошибок", "Каждая ошибка содержит решение")
    _ppt_image(slide, DOCS / "screenshot_error.png", Inches(0.65), Inches(1.6),
               Inches(8.2), Inches(5.3))
    _ppt_bullets(slide, [
        "Дубликаты баз, таблиц, полей",
        "Несуществующие объекты и id",
        "Неверные типы string/int/float/bool",
        "Пропущенные поля и лишние колонки",
        "Незакрытые кавычки и скобки",
        "Любая ошибка не завершает программу",
    ], Inches(9.1), Inches(1.8), Inches(3.7), Inches(4.8), 13, spacing=7)

    # 9. Обучение
    slide = new_slide("Интерактивное обучение", "13 шагов по всем возможностям")
    _ppt_image(slide, DOCS / "screenshot_tutorial.png", Inches(0.65), Inches(1.6),
               Inches(8.2), Inches(5.3))
    _ppt_bullets(slide, [
        "Команда шага подставляется в строку ввода",
        "Достаточно нажать Enter",
        "Проверка по реальным данным, а не по тексту",
        "Подсказка при ошибке, шаг не засчитывается",
        "TUTORIAL STOP и RESTART",
        "Посторонние команды блокируются",
    ], Inches(9.1), Inches(1.8), Inches(3.7), Inches(4.8), 13, spacing=7)

    # 10. Демо
    slide = new_slide("Демонстрация", "Команда DEMO · реестр сотрудников")
    _ppt_image(slide, DOCS / "screenshot_demo.png", Inches(0.75), Inches(1.55),
               Inches(8.6), Inches(5.4))
    _ppt_bullets(slide, [
        "База demo и таблица registry",
        "5 полей разных типов",
        "3 готовые записи",
        "Удобно для защиты проекта",
    ], Inches(9.6), Inches(1.9), Inches(3.1), Inches(3.6), 15, spacing=10)
    _ppt_text(slide, Inches(9.6), Inches(5.7), Inches(3.1), Inches(1.0),
              "CREATE → INSERT →\nSELECT → UPDATE → DELETE", 13, PACCENT, bold=True)

    # 11. Тестирование
    slide = new_slide("Тестирование", "unittest · стандартная библиотека")
    _ppt_text(slide, Inches(0.85), Inches(1.8), Inches(3.0), Inches(1.0),
              "40", 64, PGREEN, bold=True)
    _ppt_text(slide, Inches(0.9), Inches(2.9), Inches(3.2), Inches(0.6),
              "тестов, 0 ошибок", 18, PTEXT)
    _ppt_table(slide, [
        ["Группа", "Тестов"],
        ["Базы данных", "5"],
        ["Таблицы и поля", "9"],
        ["Записи и типы", "15"],
        ["Стабильность и справка", "9"],
        ["Интерактивный урок", "4"],
    ], Inches(4.4), Inches(1.75), Inches(4.3), Inches(3.9))
    _ppt_bullets(slide, [
        "Полный проход урока",
        "Дубликаты и неверные типы",
        "Строки с запятыми и кавычками",
        "Незакрытые скобки",
        "Операции с несуществующими id",
    ], Inches(9.15), Inches(1.8), Inches(3.6), Inches(4.4), 14, spacing=9)

    # 12. Преимущества
    slide = new_slide("Преимущества", "Почему решение удобно заказчику")
    _ppt_bullets(slide, [
        "Работает в изолированной среде и без установки пакетов",
        "Данные не покидают оперативную память",
        "Понятный терминал с подсказками и цветами",
        "Строгая проверка типов защищает от ошибок ввода",
        "Интерактивное обучение прямо в приложении",
        "Модульная архитектура и 42 теста",
        "Быстрый старт через DEMO",
    ], Inches(0.8), Inches(1.85), Inches(11.8), Inches(4.8), 20, spacing=8)

    # 13. Команда
    slide = new_slide("Команда проекта", "Роли и ответственность")
    _ppt_table(slide, [
        ["Участник", "Роль", "Ответственность"],
        ["Студент 1", "Руководитель, backend", "модель данных, Engine, тесты"],
        ["Студент 2", "Frontend", "GUI-терминал, оформление"],
        ["Студент 3", "Аналитик, документовед", "требования, отчёт, презентация"],
    ], Inches(0.85), Inches(1.8), Inches(11.6), Inches(2.6))

    # 14. Итог
    slide = new_slide("Результаты", "Проект готов к защите")
    _ppt_bullets(slide, [
        "Работающее приложение «РЕЕСТР»",
        "Все функциональные требования выполнены",
        "GUI-терминал и интерактивный урок",
        "42 автоматических теста",
        "Инструкция пользователя, отчёт по ГОСТ, презентация",
        "Демонстрационная база для показа",
    ], Inches(0.8), Inches(1.9), Inches(7.2), Inches(4.8), 19, spacing=9)
    _ppt_text(slide, Inches(8.3), Inches(2.1), Inches(4.3), Inches(1.2),
              "Спасибо\nза внимание!", 40, PACCENT, bold=True)
    _ppt_text(slide, Inches(8.35), Inches(4.0), Inches(4.2), Inches(1.2),
              "Готовы ответить\nна вопросы", 20, PTEXT)

    prs.save(str(out_path))
    print("saved", out_path)


# ----------------------------------------------------------------------
# Точка входа
# ----------------------------------------------------------------------
def main() -> None:
    markdown_to_docx(
        DOCS / "Инструкция_пользователя.md",
        DOCS / "Инструкция_пользователя.docx",
        gost=False,
        manual_title=True,
        skip_to_heading="## 1. Общие сведения",
    )
    markdown_to_docx(
        DOCS / "Отчет_ГОСТ.md",
        DOCS / "Отчет_ГОСТ.docx",
        gost=True,
        report_title=True,
        image_width=14.0,
    )
    markdown_to_docx(
        DOCS / "Как_объяснить_проект.md",
        DOCS / "Как_объяснить_проект.docx",
        gost=False,
    )
    markdown_to_docx(
        DOCS / "Соответствие_требованиям.md",
        DOCS / "Соответствие_требованиям.docx",
        gost=False,
        landscape=True,
    )
    markdown_to_docx(
        DOCS / "Подробный_разбор_кода.md",
        DOCS / "Подробный_разбор_кода.docx",
        gost=False,
    )
    build_presentation(DOCS / "Презентация.pptx")


if __name__ == "__main__":
    main()
