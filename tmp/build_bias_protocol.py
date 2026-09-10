from __future__ import annotations

from datetime import date
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(r"C:\Users\USER\Desktop\code\Neuroscope")
OUT = ROOT / "output" / "documents" / "neuroscope-data-collection-and-bias-protocol.docx"

INK = "172A3A"
BLUE = "2563A6"
LIGHT_BLUE = "EAF2F8"
LIGHT_GRAY = "F3F5F7"
MID_GRAY = "667085"
DARK_GRAY = "344054"
GREEN = "176B4D"
LIGHT_GREEN = "EAF6F0"
AMBER = "8A5A00"
LIGHT_AMBER = "FFF7E6"
RED = "9B2C2C"
WHITE = "FFFFFF"
BLACK = "000000"


def set_font(run, name="Arial", size=None, bold=None, italic=None, color=None):
    run.font.name = name
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.rFonts
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.insert(0, rfonts)
    rfonts.set(qn("w:ascii"), name)
    rfonts.set(qn("w:hAnsi"), name)
    rfonts.set(qn("w:eastAsia"), name)
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic
    if color is not None:
        run.font.color.rgb = RGBColor.from_string(color)


def set_cell_shading(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_margins(cell, top=100, start=120, bottom=100, end=120):
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for edge, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{edge}"))
        if node is None:
            node = OxmlElement(f"w:{edge}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_cell_width(cell, width_dxa):
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_w = tc_pr.find(qn("w:tcW"))
    if tc_w is None:
        tc_w = OxmlElement("w:tcW")
        tc_pr.append(tc_w)
    tc_w.set(qn("w:w"), str(width_dxa))
    tc_w.set(qn("w:type"), "dxa")


def configure_table(table, widths_dxa, indent_dxa=120):
    total = sum(widths_dxa)
    table.autofit = False
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    tbl_pr = table._tbl.tblPr
    tbl_layout = tbl_pr.find(qn("w:tblLayout"))
    if tbl_layout is None:
        tbl_layout = OxmlElement("w:tblLayout")
        tbl_pr.append(tbl_layout)
    tbl_layout.set(qn("w:type"), "fixed")
    tbl_w = tbl_pr.find(qn("w:tblW"))
    if tbl_w is None:
        tbl_w = OxmlElement("w:tblW")
        tbl_pr.append(tbl_w)
    tbl_w.set(qn("w:w"), str(total))
    tbl_w.set(qn("w:type"), "dxa")
    tbl_ind = tbl_pr.find(qn("w:tblInd"))
    if tbl_ind is None:
        tbl_ind = OxmlElement("w:tblInd")
        tbl_pr.append(tbl_ind)
    tbl_ind.set(qn("w:w"), str(indent_dxa))
    tbl_ind.set(qn("w:type"), "dxa")
    grid = table._tbl.tblGrid
    for child in list(grid):
        grid.remove(child)
    for width in widths_dxa:
        col = OxmlElement("w:gridCol")
        col.set(qn("w:w"), str(width))
        grid.append(col)
    for row in table.rows:
        row.height = None
        for idx, cell in enumerate(row.cells):
            set_cell_width(cell, widths_dxa[idx])
            cell.width = Inches(widths_dxa[idx] / 1440)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            set_cell_margins(cell)


def repeat_table_header(row):
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def keep_with_next(paragraph, value=True):
    paragraph.paragraph_format.keep_with_next = value


def page_break_before(paragraph):
    paragraph.paragraph_format.page_break_before = True


def shade_paragraph(paragraph, fill, border=None):
    ppr = paragraph._p.get_or_add_pPr()
    shd = ppr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        ppr.append(shd)
    shd.set(qn("w:fill"), fill)
    if border:
        pbdr = ppr.find(qn("w:pBdr"))
        if pbdr is None:
            pbdr = OxmlElement("w:pBdr")
            ppr.append(pbdr)
        left = OxmlElement("w:left")
        left.set(qn("w:val"), "single")
        left.set(qn("w:sz"), "18")
        left.set(qn("w:space"), "8")
        left.set(qn("w:color"), border)
        pbdr.append(left)


def add_callout(doc, label, text, fill=LIGHT_BLUE, accent=BLUE):
    p = doc.add_paragraph()
    p.style = doc.styles["Callout"]
    p.paragraph_format.left_indent = Inches(0.12)
    p.paragraph_format.right_indent = Inches(0.08)
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(10)
    shade_paragraph(p, fill, accent)
    r = p.add_run(label + "  ")
    set_font(r, bold=True, color=accent)
    r = p.add_run(text)
    set_font(r, color=INK)
    return p


def add_bullet(doc, text, level=0):
    p = doc.add_paragraph(style="List Bullet" if level == 0 else "List Bullet 2")
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.line_spacing = 1.12
    r = p.add_run(text)
    set_font(r, size=10.5, color=INK)
    return p


def new_decimal_num_id(doc):
    numbering = doc.part.numbering_part.element
    num_ids = [int(node.get(qn("w:numId"))) for node in numbering.findall(qn("w:num"))]
    num_id = max(num_ids, default=0) + 1
    style_num_id = str(doc.styles["List Number"]._element.pPr.numPr.numId.val)
    style_num = next(node for node in numbering.findall(qn("w:num")) if node.get(qn("w:numId")) == style_num_id)
    abstract_id = style_num.find(qn("w:abstractNumId")).get(qn("w:val"))
    num = OxmlElement("w:num")
    num.set(qn("w:numId"), str(num_id))
    abstract_ref = OxmlElement("w:abstractNumId")
    abstract_ref.set(qn("w:val"), abstract_id)
    num.append(abstract_ref)
    override = OxmlElement("w:lvlOverride")
    override.set(qn("w:ilvl"), "0")
    start_override = OxmlElement("w:startOverride")
    start_override.set(qn("w:val"), "1")
    override.append(start_override)
    num.append(override)
    numbering.append(num)
    return num_id


def apply_num_id(paragraph, num_id):
    ppr = paragraph._p.get_or_add_pPr()
    num_pr = ppr.find(qn("w:numPr"))
    if num_pr is None:
        num_pr = OxmlElement("w:numPr")
        ppr.append(num_pr)
    ilvl = OxmlElement("w:ilvl")
    ilvl.set(qn("w:val"), "0")
    num = OxmlElement("w:numId")
    num.set(qn("w:val"), str(num_id))
    num_pr.append(ilvl)
    num_pr.append(num)


def add_number(doc, lead, text, num_id):
    p = doc.add_paragraph(style="List Number")
    apply_num_id(p, num_id)
    p.paragraph_format.space_after = Pt(5)
    p.paragraph_format.line_spacing = 1.12
    r = p.add_run(lead + ": ")
    set_font(r, size=10.5, bold=True, color=INK)
    r = p.add_run(text)
    set_font(r, size=10.5, color=INK)
    return p


def add_body(doc, text, bold_lead=None):
    p = doc.add_paragraph()
    if bold_lead and text.startswith(bold_lead):
        r = p.add_run(bold_lead)
        set_font(r, size=10.5, bold=True, color=INK)
        r = p.add_run(text[len(bold_lead):])
        set_font(r, size=10.5, color=INK)
    else:
        r = p.add_run(text)
        set_font(r, size=10.5, color=INK)
    return p


def add_heading(doc, text, level=1):
    p = doc.add_paragraph(text, style=f"Heading {level}")
    keep_with_next(p)
    return p


def add_hyperlink(paragraph, text, url, color=BLUE):
    part = paragraph.part
    rid = part.relate_to(url, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink", is_external=True)
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), rid)
    run = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    c = OxmlElement("w:color")
    c.set(qn("w:val"), color)
    rpr.append(c)
    u = OxmlElement("w:u")
    u.set(qn("w:val"), "single")
    rpr.append(u)
    rfonts = OxmlElement("w:rFonts")
    rfonts.set(qn("w:ascii"), "Arial")
    rfonts.set(qn("w:hAnsi"), "Arial")
    rpr.append(rfonts)
    run.append(rpr)
    t = OxmlElement("w:t")
    t.text = text
    run.append(t)
    hyperlink.append(run)
    paragraph._p.append(hyperlink)


def add_page_field(paragraph):
    run = paragraph.add_run()
    fld_char1 = OxmlElement("w:fldChar")
    fld_char1.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = " PAGE "
    fld_char2 = OxmlElement("w:fldChar")
    fld_char2.set(qn("w:fldCharType"), "end")
    run._r.append(fld_char1)
    run._r.append(instr)
    run._r.append(fld_char2)
    set_font(run, size=9, color=MID_GRAY)


def style_document(doc):
    section = doc.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(0.86)
    section.bottom_margin = Inches(0.82)
    section.left_margin = Inches(0.95)
    section.right_margin = Inches(0.95)
    section.header_distance = Inches(0.40)
    section.footer_distance = Inches(0.40)

    normal = doc.styles["Normal"]
    normal.font.name = "Arial"
    normal._element.rPr.rFonts.set(qn("w:ascii"), "Arial")
    normal._element.rPr.rFonts.set(qn("w:hAnsi"), "Arial")
    normal.font.size = Pt(10.5)
    normal.font.color.rgb = RGBColor.from_string(INK)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.10

    title = doc.styles["Title"]
    title.font.name = "Arial"
    title._element.rPr.rFonts.set(qn("w:ascii"), "Arial")
    title._element.rPr.rFonts.set(qn("w:hAnsi"), "Arial")
    title.font.size = Pt(25)
    title.font.bold = True
    title.font.color.rgb = RGBColor.from_string(INK)
    title.paragraph_format.space_after = Pt(6)
    title_ppr = title._element.get_or_add_pPr()
    title_pbdr = title_ppr.find(qn("w:pBdr"))
    if title_pbdr is None:
        title_pbdr = OxmlElement("w:pBdr")
        title_ppr.append(title_pbdr)
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "nil")
    title_pbdr.append(bottom)

    subtitle = doc.styles["Subtitle"]
    subtitle.font.name = "Arial"
    subtitle._element.rPr.rFonts.set(qn("w:ascii"), "Arial")
    subtitle._element.rPr.rFonts.set(qn("w:hAnsi"), "Arial")
    subtitle.font.size = Pt(13)
    subtitle.font.color.rgb = RGBColor.from_string(DARK_GRAY)
    subtitle.paragraph_format.space_after = Pt(16)

    for level, size, before, after, color in (
        (1, 16, 12, 6, BLUE),
        (2, 13, 10, 5, BLUE),
        (3, 11.5, 8, 4, DARK_GRAY),
    ):
        style = doc.styles[f"Heading {level}"]
        style.font.name = "Arial"
        style._element.rPr.rFonts.set(qn("w:ascii"), "Arial")
        style._element.rPr.rFonts.set(qn("w:hAnsi"), "Arial")
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor.from_string(color)
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)
        style.paragraph_format.keep_with_next = True

    for list_name in ("List Bullet", "List Bullet 2", "List Number"):
        style = doc.styles[list_name]
        style.font.name = "Arial"
        style._element.rPr.rFonts.set(qn("w:ascii"), "Arial")
        style._element.rPr.rFonts.set(qn("w:hAnsi"), "Arial")
        style.font.size = Pt(10.5)
        style.paragraph_format.space_after = Pt(4)
        style.paragraph_format.line_spacing = 1.12

    if "Callout" not in [s.name for s in doc.styles]:
        callout = doc.styles.add_style("Callout", 1)
    else:
        callout = doc.styles["Callout"]
    callout.font.name = "Arial"
    callout._element.rPr.rFonts.set(qn("w:ascii"), "Arial")
    callout._element.rPr.rFonts.set(qn("w:hAnsi"), "Arial")
    callout.font.size = Pt(10.5)
    callout.paragraph_format.line_spacing = 1.10

    header = section.header
    hp = header.paragraphs[0]
    hp.alignment = WD_ALIGN_PARAGRAPH.LEFT
    hr = hp.add_run("NEUROSCOPE  /  STUDY DESIGN DECISION")
    set_font(hr, size=8.5, bold=True, color=MID_GRAY)

    footer = section.footer
    fp = footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    fr = fp.add_run("Internal protocol  |  Page ")
    set_font(fr, size=9, color=MID_GRAY)
    add_page_field(fp)


def add_title_block(doc):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(18)
    p.paragraph_format.space_after = Pt(6)
    r = p.add_run("DECISION MEMO")
    set_font(r, size=9, bold=True, color=BLUE)

    p = doc.add_paragraph(style="Title")
    p.add_run("Data Collection and Bias-Reduction Protocol")
    p = doc.add_paragraph(style="Subtitle")
    p.add_run("A defensible school-based design for NEUROSCOPE students, teachers, and model validation")

    rows = [
        ("Decision owner", "NEUROSCOPE research team"),
        ("Audience", "Principal / school research reviewer / project mentors"),
        ("Status", "Recommended protocol for approval and preregistration"),
        ("Prepared", date.today().strftime("%d %B %Y")),
    ]
    for label, value in rows:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(2)
        r = p.add_run(f"{label}: ")
        set_font(r, size=9.5, bold=True, color=DARK_GRAY)
        r = p.add_run(value)
        set_font(r, size=9.5, color=DARK_GRAY)
    doc.add_paragraph()


def add_tldr(doc):
    add_heading(doc, "TL;DR", 1)
    add_callout(
        doc,
        "Decision",
        "Run a 1-2 day feasibility pilot immediately, then complete a time-boxed main study before the science-fair cutoff using roster-based random invitations. Develop the primary model on students; invite every eligible teacher into a separate exploratory adult cohort. Do not use an open class-group link as the sampling method.",
        LIGHT_GREEN,
        GREEN,
    )
    bullets = [
        "Define the primary target as enrolled students in this school, not 'humans' in general. Teacher results answer a separate transfer question unless a much larger adult sample is collected.",
        "Select students within grade and section from a roster, issue one-time invitation codes, and use class-group posts only as reminders to selected people. Track invitation, consent, start, and completion rates by stratum.",
        "Invite all teachers privately and repeatedly across neutral time slots. A small teacher cohort is not repaired by copying, SMOTE, or forcing equal student/teacher counts; report it as exploratory with wide confidence intervals.",
        "Use supervised, quiet computer-lab sessions on standard devices, spread across several low-disruption time blocks before exams. Record the block, device, browser, interruptions, task order, and app version.",
        "Counterbalance the five task orders. The current fixed order makes task identity inseparable from fatigue and position, so the final task can look different simply because it is last.",
        "Ask role first. For students, collect grade/section plus completed age or narrow student age bands. For teachers, use broad adult age bands. Never use age as a substitute for role.",
        "Split and resample by participant, never by trial. With a modest sample, use repeated nested participant-level cross-validation; with enough data, add a locked untouched test set. A few students cannot validate teacher performance.",
        "Report uncertainty, sampling weights, subgroup performance, completion bias, and simple baselines. If the school yields fewer than roughly 150 completed student sessions, frame the Transformer as a feasibility result rather than a validated general model.",
        "For participants under 18, obtain the locally required parent/guardian consent and the student's assent through an approved process. The deadline does not justify bypassing review, and the current self-attested guardian checkbox should not be treated as sufficient without formal school/ethics approval.",
    ]
    for item in bullets:
        add_bullet(doc, item)


def add_decision_logic(doc):
    add_heading(doc, "1. What is actually biased - and what is not", 1)
    add_body(doc, "More students than teachers is not automatically bias. It is the real composition of a school. Bias appears when the sample is produced by unequal self-selection, when the model's target population is left vague, or when performance from a student-heavy sample is presented as if it applies equally to teachers or to the wider public.")
    add_body(doc, "The main design decision is therefore to separate the scientific questions. The primary question should be whether NEUROSCOPE learns useful cross-task representations among enrolled students. A second, exploratory question can ask whether a student-developed representation transfers to teachers. Combining the cohorts and reporting one score would hide the population shift because age, role, schedule, and educational experience are nearly confounded.")
    add_callout(doc, "Claim boundary", "A representative sample from one school supports inference to that school's sampled student population under the stated conditions. It does not establish a representation of all human decision-making. Broader claims require independent schools, adult community participants, and temporal replication.", LIGHT_AMBER, AMBER)

    add_heading(doc, "Why the proposed 'train on everyone, validate on a few students' design fails", 2)
    num_id = new_decimal_num_id(doc)
    add_number(doc, "It cannot test teachers", "A student-only validation subset estimates performance on new students, not on teachers. The teacher domain remains untested if teacher records were used during training.", num_id)
    add_number(doc, "A few cases give unstable results", "With small samples, cross-validation estimates have large error bars; a seemingly consistent score can change sharply under another split.", num_id)
    add_number(doc, "Validation is not a reasoning check", "The test must use a predeclared measurable target, an untouched participant set or an outer cross-validation loop, and uncertainty intervals. Reading model explanations and deciding that they look consistent is qualitative inspection, not evidence of generalization.", num_id)
    add_number(doc, "The current code answers a narrower question", "The encoder is pretrained on all five tasks, then the probe predicts a participant's behavior in one task from the other four. That is cross-task prediction within a task-aware model, not proof that the model generalizes to a task it has never seen.", num_id)


def add_population_sampling(doc):
    add_heading(doc, "2. Population and sampling decision", 1)
    add_heading(doc, "Primary and secondary cohorts", 2)
    table = doc.add_table(rows=1, cols=4)
    table.style = "Table Grid"
    hdr = table.rows[0].cells
    for i, text in enumerate(("Cohort", "Recruitment", "Analytical role", "Permitted claim")):
        hdr[i].text = text
        set_cell_shading(hdr[i], LIGHT_BLUE)
    rows = [
        ("Students", "Stratified random sample from grade/section rosters", "Primary development and internal evaluation cohort", "New students from the same school and sampling frame"),
        ("Teachers", "Census invitation to all eligible teachers", "Separate exploratory transfer cohort; keep out of primary training", "Observed teachers only, with uncertainty; no broad adult claim"),
        ("Retest subset", "Random subsample of consenting students", "Behavioral stability, using alternate seeds/stimuli", "Test-retest stability over the chosen interval"),
    ]
    for row in rows:
        cells = table.add_row().cells
        for i, value in enumerate(row):
            cells[i].text = value
    configure_table(table, [1420, 2620, 2740, 2580])
    repeat_table_header(table.rows[0])
    for row_idx, row in enumerate(table.rows):
        for cell in row.cells:
            for p in cell.paragraphs:
                p.paragraph_format.space_after = Pt(2)
                for run in p.runs:
                    set_font(run, size=9, bold=(row_idx == 0), color=INK)

    add_heading(doc, "Student selection procedure", 2)
    num_id = new_decimal_num_id(doc)
    add_number(doc, "Build the frame", "Obtain counts and pseudonymous roster IDs by grade and section as of one stated date. Researchers do not need names in the analysis file; the school can hold the invite mapping.", num_id)
    add_number(doc, "Set strata", "Use grade as the minimum stratum and section as a blocking variable. If gender or another protected attribute is important and ethically approved, monitor representation without publishing small identifiable cells.", num_id)
    add_number(doc, "Allocate invitations", "Start with proportional allocation, n_h = n(N_h/N). Apply a minimum per grade only when subgroup precision is required; any oversampling must be accompanied by known selection probabilities.", num_id)
    add_number(doc, "Select randomly", "Use a reproducible random seed to draw primary invitees and ordered alternates within each stratum. Replacements must come from the same stratum, so absence does not quietly change the sample composition.", num_id)
    add_number(doc, "Issue private codes", "Give each selected person a one-time invitation code. A class-group post may remind selected participants, but the link must not admit anyone who was not sampled.", num_id)
    add_number(doc, "Track the denominator", "For every stratum, retain counts for eligible, invited, guardian-approved where applicable, assented/consented, started, completed, and excluded. Without these denominators, nonresponse bias cannot be assessed.", num_id)

    add_heading(doc, "Teacher recruitment", 2)
    add_body(doc, "Invite every eligible teacher because the staff population is small. Invitations should be private, voluntary, and available in multiple time slots; the principal should not receive a list of participants. Report the teacher response rate against the number eligible. If very few teachers complete the study, keep the results descriptive and exploratory rather than blending them into a student-heavy headline score.")
    add_body(doc, "Do not manufacture balance by duplicating teacher sessions, splitting one teacher's 240 trials across different folds, or using synthetic oversampling. Those operations make the training table look balanced while the number of independent adults remains unchanged.")


def add_timing_environment(doc):
    add_heading(doc, "3. Collection timing and experimental environment", 1)
    add_callout(doc, "Scheduling decision", "Ask for expedited approval now, run a 1-2 day feasibility pilot, and complete the main collection before the science-fair data cutoff. Because the exam period cannot be avoided, spread sessions across several blocks, record exam proximity and time of day, and limit the claim to behavior collected under this pre-exam school context.", LIGHT_GREEN, GREEN)

    add_heading(doc, "Two-stage rollout", 2)
    table = doc.add_table(rows=1, cols=4)
    table.style = "Table Grid"
    for i, text in enumerate(("Stage", "Timing", "Size / purpose", "Go/no-go output")):
        table.rows[0].cells[i].text = text
        set_cell_shading(table.rows[0].cells[i], LIGHT_BLUE)
    rows = [
        ("Feasibility pilot", "Days 1-2, once approved", "About 8-12 sessions across grades and adults; do not estimate model validity", "Duration, dropout points, instruction failures, device issues, RT distributions"),
        ("Main collection", "Next 7-10 school days, ending before the analysis cutoff", "Roster-selected students plus teacher census; practical aim 60-100 completed students if capacity permits", "Frozen preliminary dataset with recorded sampling probabilities"),
        ("Retest / replication", "Only if a full 7-day interval fits; otherwise after submission", "Random consenting student subset with alternate seeds/stimuli", "Future stability evidence; do not imply it was completed in the fair submission"),
    ]
    for row in rows:
        cells = table.add_row().cells
        for i, value in enumerate(row):
            cells[i].text = value
    configure_table(table, [1700, 1750, 3220, 2690])
    repeat_table_header(table.rows[0])
    for row_idx, row in enumerate(table.rows):
        for cell in row.cells:
            for p in cell.paragraphs:
                p.paragraph_format.space_after = Pt(2)
                for run in p.runs:
                    set_font(run, size=9, bold=(row_idx == 0), color=INK)

    add_heading(doc, "Standard session protocol", 2)
    standards = [
        "Use a quiet computer room with the same device class, browser version, input method, screen size range, seating separation, lighting, and instruction script. The goal is to reduce avoidable measurement variance, especially in reaction time.",
        "Offer several neutral time blocks across the day and randomly allocate selected participants within practical constraints. Do not use zero period as the only block, because availability and morning attendance would become selection variables.",
        "Record session block, room, device ID/class, browser, viewport, input method, network interruptions, proctor, experiment version, task order, breaks, and self-reported interruption count. These fields let the analysis detect and adjust for environment drift.",
        "Give the same short practice for each task and exclude practice trials from analysis. Proctors may resolve technical issues but should not explain strategies or watch a participant's choices.",
        "Permit withdrawal without penalty and make the screen arrangement private. Teacher presence during student choice tasks can alter social and authority-sensitive behavior, so teachers should not circulate as observers.",
    ]
    for item in standards:
        add_bullet(doc, item)

    add_heading(doc, "Counterbalance task order", 2)
    add_body(doc, "The current application runs probabilistic learning, risk preference, delay discounting, rule discovery, and social ultimatum in one fixed order. Because the position is identical for everyone, task effects are perfectly entangled with fatigue, practice, and elapsed time. Use five balanced order sequences, such as a Latin-square rotation, assign them within grade and session block, and store the assigned order. If this change cannot be validated within 48 hours, keep one fixed order for the entire time-boxed study, record it as a major limitation, and do not compare tasks as though position had no effect; a rushed untested ordering change could create a worse protocol failure.")


def add_demographics(doc):
    add_heading(doc, "4. Age categories and demographic fields", 1)
    add_body(doc, "The current app uses 13-17, 18-24, 25-34, and successive adult bands. That scheme is too coarse for students, collects many adult categories that the school may barely populate, and lets age stand in for role. Developmental work shows that probabilistic learning, risk preference, and delay discounting can change within adolescence, so one 13-17 bin can hide relevant differences.")
    add_callout(doc, "UI decision", "Ask 'Are you participating as a student or teacher?' first, then show cohort-specific fields. Store role directly. Do not infer it from age or education level.", LIGHT_BLUE, BLUE)

    table = doc.add_table(rows=1, cols=4)
    table.style = "Table Grid"
    for i, text in enumerate(("Field", "Students", "Teachers", "Reason")):
        table.rows[0].cells[i].text = text
        set_cell_shading(table.rows[0].cells[i], LIGHT_BLUE)
    rows = [
        ("Role", "student", "teacher", "Essential cohort variable; prevents age-role confounding in the data schema"),
        ("Age", "Completed years 13, 14, 15, 16, 17, 18 if approved; publish as 13-14, 15-16, 17-18", "20-29, 30-39, 40-49, 50-59, 60+; optional if cells are identifying", "Student years preserve developmental resolution; broad staff bands protect privacy"),
        ("School level", "Grade/year required; section stored as a pseudonymous sampling block", "Broad department or teaching level only if analytically needed", "Grade/section supports sampling and nonresponse analysis"),
        ("Education", "Remove the current adult-oriented highest-education question", "Optional broad qualification categories", "The present question has little variation among students and can leak role"),
        ("Environment", "Session block, room/device, task order", "Same fields", "Needed to separate cohort effects from collection-condition effects"),
    ]
    for row in rows:
        cells = table.add_row().cells
        for i, value in enumerate(row):
            cells[i].text = value
    configure_table(table, [1250, 2720, 2500, 2890])
    repeat_table_header(table.rows[0])
    for row_idx, row in enumerate(table.rows):
        for cell in row.cells:
            for p in cell.paragraphs:
                p.paragraph_format.space_after = Pt(2)
                for run in p.runs:
                    set_font(run, size=8.6, bold=(row_idx == 0), color=INK)

    add_body(doc, "If changing the schema is impossible before the pilot, retain the current age values for the pilot only, add role and grade immediately, and define a clean migration before the main dataset. Never combine pilot and main records without an experiment-version field.")
    add_body(doc, "Protect small cells. Do not publish cross-tabs that make a teacher identifiable; suppress or combine cells below a preregistered threshold such as n < 5, and use a stricter threshold when the school is very small.")


def add_validation(doc):
    add_heading(doc, "5. Training, validation, and generalization", 1)
    add_heading(doc, "Use two independent validation questions", 2)
    num_id = new_decimal_num_id(doc)
    add_number(doc, "New-participant prediction", "Can a pipeline fitted without a participant predict that participant's held-out behavior? This requires participant-level splits, with every trial from one person kept in one outer fold.", num_id)
    add_number(doc, "Test-retest stability", "Does the same person's representation remain similar at a later session? This requires a linkable pseudonymous retest ID, a fixed interval, alternate task seeds/stimuli, and explicit analysis of practice effects. It is not the same as a model test set.", num_id)

    add_heading(doc, "Recommended evaluation by completed student N", 2)
    table = doc.add_table(rows=1, cols=3)
    table.style = "Table Grid"
    for i, text in enumerate(("Completed students", "Evaluation design", "Interpretation")):
        table.rows[0].cells[i].text = text
        set_cell_shading(table.rows[0].cells[i], LIGHT_BLUE)
    rows = [
        ("Below 80", "Repeated nested participant-level cross-validation; very small hyperparameter search; permutation and simple baselines", "Feasibility only. Expect wide intervals and do not claim a validated Transformer."),
        ("80-149", "Repeated nested 5-fold participant-level CV stratified by grade and target label where possible", "Exploratory model comparison; report split-to-split variability and bootstrap CIs."),
        ("150-299", "Lock about 15% before analysis if every important stratum remains represented; tune only within the remaining nested CV", "One untouched test estimate plus internal uncertainty; subgroup claims may still be underpowered."),
        ("300 or more", "Lock 20% stratified test set; nested CV on development data; consider a later school or cohort as external evaluation", "Stronger within-school evidence, still not population-wide human generalization."),
    ]
    for row in rows:
        cells = table.add_row().cells
        for i, value in enumerate(row):
            cells[i].text = value
    configure_table(table, [1500, 4410, 3450])
    repeat_table_header(table.rows[0])
    for row_idx, row in enumerate(table.rows):
        for cell in row.cells:
            for p in cell.paragraphs:
                p.paragraph_format.space_after = Pt(2)
                for run in p.runs:
                    set_font(run, size=8.8, bold=(row_idx == 0), color=INK)

    add_callout(doc, "These are decision thresholds, not power calculations", "The required N depends on the primary target, event prevalence, candidate model complexity, expected performance, and desired precision. Final sample size should be set by simulation or a formal power/precision analysis after the feasibility pilot supplies completion rates and outcome distributions.", LIGHT_AMBER, AMBER)

    add_heading(doc, "Required split rules", 2)
    split_rules = [
        "Create the outer split before any normalization, vocabulary fitting, feature selection, model selection, or threshold choice. Refit every data-dependent step inside each training fold.",
        "Keep all 240 trials and every retest from one participant in the same outer fold unless the explicit task is longitudinal forecasting. Trial-level random splits leak participant signatures.",
        "Stratify student folds by grade and the probe target when feasible. Do not require teacher balance inside student folds; teachers are a separate transfer set.",
        "Use the validation folds for hyperparameters and early stopping. Touch the locked test set once after the analysis plan and model family are frozen.",
        "Report the full distribution across repeated outer splits, participant-level bootstrap confidence intervals, and simple baselines. One favorable seed is not a result.",
    ]
    for item in split_rules:
        add_bullet(doc, item)

    add_heading(doc, "Code-specific implications", 2)
    add_body(doc, "The current dataset splitter in ml/utils/dataset.py performs a seeded random participant split, but it does not stratify by grade, role, or label. The evaluation in ml/utils/evaluate.py creates another 70/30 split or leave-one-out calculation and reports a majority baseline. Before the main analysis, replace this with a preregistered participant-aware nested scheme and preserve one immutable split manifest containing participant IDs, strata, and seed.")
    add_body(doc, "The current extraction query in ml/utils/extract.py keeps only perfectly completed 240-trial sessions. That is acceptable for a complete-sequence training tensor, but it hides attrition unless partial sessions and their last completed task are retained in a separate quality table. Analyze completion probability by grade, role, time block, device, and order; otherwise the final model may represent only participants willing and able to finish the full battery.")
    add_body(doc, "The existing held-out-task probe removes one task while pooling a participant's other hidden states, but the encoder itself was pretrained on all tasks. Name the result 'cross-task behavioral prediction' unless the full encoder-training protocol also excludes the target task or an entirely new task is evaluated.")


def add_statistics(doc):
    add_heading(doc, "6. Statistical techniques and reporting", 1)
    add_heading(doc, "Sampling and nonresponse weights", 2)
    add_body(doc, "For student stratum h with N_h eligible students and n_h randomly selected invitations, the inclusion probability is pi_h = n_h/N_h and the base design weight is w_h = 1/pi_h. Adjust weights for response within preregistered cells, calibrate to known roster totals if needed, and trim only under a declared rule. Use weights for population descriptions and sensitivity analyses; do not assume that weighting can repair unmeasured self-selection.")
    add_body(doc, "Report the effective sample size after weighting: n_eff = (sum w_i)^2 / sum(w_i^2). Large weight variation can make a nominal sample look much larger than the information it contains. When whole classes are sampled, account for clustering; a planning approximation is design effect DE = 1 + (m - 1)ICC, where m is average class size and ICC is within-class correlation.")

    add_heading(doc, "Core analysis set", 2)
    analyses = [
        "Publish a recruitment flow by cohort and stratum: eligible, invited, consented/assented, started, completed, technically excluded, and analyzed. Compare respondents with the sampling frame on variables known for both groups.",
        "Describe task outcomes separately for students and teachers. For student population summaries, show unweighted and weighted estimates with participant-level confidence intervals.",
        "Use mixed-effects or hierarchical models for trial outcomes, with participant random effects and fixed effects for task position, elapsed time, session block, device class, experiment version, and age/grade when justified. Trials are repeated measurements, not 240 independent participants.",
        "For classification probes, report balanced accuracy and macro-F1 alongside accuracy and the majority baseline. Add calibration or continuous error metrics when the target is probabilistic or continuous. Use permutation tests that preserve participant grouping.",
        "For embedding stability, report intraclass correlation or an appropriate similarity measure with bootstrap confidence intervals, and distinguish test-retest agreement from mere correlation.",
        "Run sensitivity analyses for complete cases versus completion-propensity weighting, weighted versus unweighted student estimates, fixed-order pilot exclusion, RT handling, and different reasonable split seeds.",
        "Predeclare exclusion rules from the pilot: duplicate/corrupt records, technical failure, impossible response times, comprehension failure, and excessive missingness. Log-transform heavy-tailed RTs; avoid deleting slow valid responses simply because they are inconvenient.",
    ]
    for item in analyses:
        add_bullet(doc, item)

    add_heading(doc, "Sample-size planning", 2)
    add_body(doc, "Do not calculate model sample size from 240 trials per person as if N were 240 times the number of participants. Generalization to a new person depends mainly on the number of independent participants. Use the pilot to estimate completion, label balance, variance, class/section ICC, and learning-curve behavior; then simulate the full pipeline at candidate participant counts and choose N for a predeclared precision target.")
    add_body(doc, "For a descriptive student proportion, a conventional starting point is n0 = z^2 p(1-p)/e^2, followed by the finite-population correction n = n0 / [1 + (n0 - 1)/N] and inflation for nonresponse and clustering. That formula does not size a Transformer; it only helps plan descriptive precision.")


def add_bias_register(doc):
    add_heading(doc, "7. Bias register and controls", 1)
    table = doc.add_table(rows=1, cols=4)
    table.style = "Table Grid"
    for i, text in enumerate(("Bias", "How it enters NEUROSCOPE", "Design control", "Analysis / disclosure")):
        table.rows[0].cells[i].text = text
        set_cell_shading(table.rows[0].cells[i], LIGHT_BLUE)
    rows = [
        ("Self-selection", "Open class-group link attracts interested, available, high-engagement participants", "Roster sampling, private codes, ordered alternates", "Response rates and frame comparisons by stratum"),
        ("Coverage", "Students without easy phone/device access or absent from groups are missed", "School devices and roster frame", "Document exclusions from the frame"),
        ("Guardian-consent", "Minor participation may vary by family availability or attitudes", "Simple approved materials, equal reminders, no coercion", "Track consent return by grade without sensitive family profiling"),
        ("Teacher nonresponse", "Busy staff participate selectively", "Teacher census, several slots, privacy from management", "Report eligible and completed counts; exploratory inference"),
        ("Exam-period", "Stress and availability alter choices and completion", "Several pre-exam blocks; fixed cutoff; no open-link rush", "Record date/block and exam proximity; bound claims to this context"),
        ("Environment/device", "RT and attention vary across phones, laptops, rooms, and interruptions", "Standard lab devices; consistent script", "Device/block covariates and sensitivity analysis"),
        ("Order/fatigue", "Fixed last task is always measured after the longest exposure", "Balanced task-order assignment", "Include position/elapsed time; test order interactions"),
        ("Attrition", "Only perfect 240-trial sessions enter current extraction", "Retain partial-session QC metadata", "Completion model and inverse-probability sensitivity"),
        ("Age-role confounding", "Most students are minors and most teachers are adults", "Separate cohorts; collect role directly", "No causal age-vs-role interpretation without overlap"),
        ("Leakage", "Trials from one person appear in train and test, or preprocessing sees test data", "Participant-level split manifest", "Replay full pipeline inside folds"),
        ("Small-sample optimism", "Many model/seed choices produce a lucky score", "Preregister targets and limited tuning", "Nested CV, uncertainty, permutation baseline"),
        ("Reporting", "One aggregate score hides weak grades or cohorts", "Subgroup evaluation plan", "Counts and CIs; suppress identifying small cells"),
    ]
    for row in rows:
        cells = table.add_row().cells
        for i, value in enumerate(row):
            cells[i].text = value
    configure_table(table, [1380, 2800, 2510, 2670])
    repeat_table_header(table.rows[0])
    for row_idx, row in enumerate(table.rows):
        for cell in row.cells:
            for p in cell.paragraphs:
                p.paragraph_format.space_after = Pt(1)
                p.paragraph_format.line_spacing = 1.0
                for run in p.runs:
                    set_font(run, size=8.1, bold=(row_idx == 0), color=INK)


def add_ethics(doc):
    add_heading(doc, "8. Consent, assent, privacy, and school approval", 1)
    add_body(doc, "This is behavioral research involving minors, so the school should approve the protocol, recruitment language, data fields, retention period, and withdrawal process before main collection. The locally applicable ethics authority and school policy determine the exact process. Where the ICMR child-research guidance applies, parent/LAR permission and the child's assent are distinct requirements, and information should be understandable and voluntary.")
    add_body(doc, "The app currently asks a 13-17-year-old to tick a box stating that a guardian consented. Treat that as a UI acknowledgement, not proof that an approved guardian-consent process occurred. Use signed or otherwise auditable consent outside the analysis dataset, provide the student an age-appropriate assent screen, and store only a consent-status token in NEUROSCOPE.")
    add_body(doc, "Participation must not affect grades, teacher evaluation, attendance, or access to activities. Recruitment by authority figures should make refusal private, and incentives should be modest and equal across cohorts. Keep the school-held invite mapping separate from the research database, define a deletion/retention schedule, restrict exports, and suppress small teacher cells.")


def add_implementation(doc):
    add_heading(doc, "9. Action plan for the next four weeks", 1)
    steps = [
        ("Day 0-1 - expedited approval packet", "Send the principal a two-page operational summary: pre-exam time-boxed collection, 8-12-person feasibility pilot, room/device needs, consent/assent workflow, teacher privacy, and low-disruption session blocks. Ask for roster counts by grade/section, not names."),
        ("Day 1 - analysis lock", "Freeze the target population, primary model question, recruitment frame, exclusion rules, participant-level split policy, target metrics, and claim boundaries before seeing main outcomes."),
        ("Day 1-2 - minimum app changes", "Prioritize role, grade/section block, invitation code, environment metadata, experiment version, partial-session status, and a split manifest. Add counterbalanced order only if it can be tested safely within 48 hours."),
        ("Day 2-3 - feasibility pilot", "Run 8-12 approved sessions and inspect duration, dropout, misunderstanding, RT/device behavior, and data integrity. Correct protocol-breaking defects, then version and freeze the main app."),
        ("Day 3-12 - main sessions", "Run several standardized blocks during permitted zero periods, free/study periods, lunch, or other low-disruption windows; zero period must not be the only option. Use same-stratum alternates and maintain recruitment counts without optimizing on outcomes."),
        ("Two to three days before submission - data cutoff", "Stop recruitment at a declared timestamp, hash and freeze the raw export, code version, exclusion log, and split manifest. Late sessions belong to a later replication, not the submitted analysis."),
        ("Final 48-72 hours - analysis", "Use the predeclared nested participant-level evaluation and simple baselines. If N is small, lead with feasibility, data quality, descriptive task patterns, and uncertainty instead of a single optimistic model score."),
        ("Submission - report", "Present student and teacher cohorts separately, label all results preliminary, publish uncertainty and limitations, and state that the exam-adjacent school setting bounds the evidence."),
    ]
    num_id = new_decimal_num_id(doc)
    for lead, text in steps:
        add_number(doc, lead, text, num_id)

    add_heading(doc, "Approval fallback", 2)
    add_body(doc, "If the principal does not approve student collection in time, submit the science-fair project as a validated data-collection and ML feasibility pipeline using synthetic QA data plus any separately approved adult usability pilot. Do not turn a class-group convenience sample into the main dataset or imply that synthetic sessions validate human behavior. The fair submission can present the research question, working system, preregistered protocol, and clearly labeled preliminary evidence.")


def add_acceptance(doc):
    add_heading(doc, "10. Minimum acceptance criteria before main launch", 1)
    checks = [
        "The target population and permitted claims are written in one paragraph and approved.",
        "A roster-based sampling frame, selection seed, stratum counts, and alternate lists exist.",
        "Teacher invitations are separate, private, and census-based.",
        "The consent/assent workflow is approved; minor participation is not based only on self-attestation.",
        "Role, grade/section block, revised ages, invitation status, environment, task order, and experiment version are logged.",
        "Five balanced task orders have passed testing, or the fixed-order pilot is explicitly excluded from main inference.",
        "Partial sessions and dropout stage can be counted without exposing trial records to the browser.",
        "The participant-level split manifest and nested evaluation code are tested on synthetic data.",
        "A simple baseline, balanced metrics, uncertainty intervals, and subgroup reporting rules are preregistered.",
        "No one has opened or optimized against the locked test set.",
    ]
    for item in checks:
        add_bullet(doc, "[ ] " + item)


def add_sources(doc):
    add_heading(doc, "Sources and evidence base", 1)
    add_body(doc, "The recommendations combine the NEUROSCOPE implementation and study brief with the following methodological and empirical sources. Web sources were checked on 30 August 2026.")
    sources = [
        ("NEUROSCOPE repository study brief and implementation", "Local sources: README.md; web/docs/idea.pdf; web/lib/constants.ts; web/components/consent/consent-form.tsx; ml/utils/dataset.py; ml/utils/extract.py; ml/utils/evaluate.py."),
        ("ICMR, National Ethical Guidelines for Biomedical Research Involving Children", "https://www.icmr.gov.in/icmrobject/custom_data/pdf/resource-guidelines/National_Ethical_Guidelines_for_BioMedical_Research_Involving_Children_0.pdf"),
        ("von Elm et al., STROBE Statement", "https://www.equator-network.org/reporting-guidelines/strobe/"),
        ("AAPOR Task Force on Non-Probability Sampling", "https://aapor.org/wp-content/uploads/2022/11/NPS_TF_Report_Final_7_revised_FNL_6_22_13.pdf"),
        ("NCES Handbook of Survey Methods - School and Staffing Survey design", "https://nces.ed.gov/statprog/handbook/sass_surveydesign.asp"),
        ("European Social Survey - weighting", "https://www.europeansocialsurvey.org/methodology/ess-methodology/data-processing-and-archiving/weighting"),
        ("Riley et al. (2020), Calculating sample size for prediction model development", "https://www.bmj.com/content/368/bmj.m441"),
        ("Varoquaux (2018), Cross-validation failure: small samples lead to large error bars", "https://pubmed.ncbi.nlm.nih.gov/28655633/"),
        ("Collins et al. (2024), TRIPOD+AI statement", "https://pmc.ncbi.nlm.nih.gov/articles/PMC11019967/"),
        ("Frontiers (2024), Data leakage in repeated-measures deep learning", "https://www.frontiersin.org/journals/neuroscience/articles/10.3389/fnins.2024.1373515/full"),
        ("Bridges et al. (2020), Timing mega-study of lab and online experiment generators", "https://pubmed.ncbi.nlm.nih.gov/33005482/"),
        ("Sievertsen et al. (2016), Cognitive fatigue and student test performance", "https://pmc.ncbi.nlm.nih.gov/articles/PMC4790980/"),
        ("van den Bos et al. (2012), Decision-making under risk across development", "https://pmc.ncbi.nlm.nih.gov/articles/PMC3110498/"),
        ("Davidow et al. (2021), Probabilistic reinforcement learning across ages 8-30", "https://pmc.ncbi.nlm.nih.gov/articles/PMC8279421/"),
        ("de Water et al. (2014), Age and educational track in adolescent delay discounting", "https://pmc.ncbi.nlm.nih.gov/articles/PMC3872775/"),
    ]
    num_id = new_decimal_num_id(doc)
    for idx, (label, url) in enumerate(sources, start=1):
        p = doc.add_paragraph(style="List Number")
        apply_num_id(p, num_id)
        p.paragraph_format.space_after = Pt(4)
        r = p.add_run(label + ". ")
        set_font(r, size=9.2, color=INK)
        if url.startswith("http"):
            add_hyperlink(p, "Open source", url)
        else:
            r = p.add_run(url)
            set_font(r, size=9.2, color=DARK_GRAY)


def build():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = Document()
    doc.settings.odd_and_even_pages_header_footer = False
    style_document(doc)
    doc.core_properties.title = "NEUROSCOPE Data Collection and Bias-Reduction Protocol"
    doc.core_properties.subject = "School-based sampling, experimental environment, demographics, and model validation"
    doc.core_properties.author = "NEUROSCOPE research team"
    doc.core_properties.keywords = "sampling bias, school research, validation, behavioral data, NEUROSCOPE"

    add_title_block(doc)
    add_tldr(doc)
    add_decision_logic(doc)
    add_population_sampling(doc)
    add_timing_environment(doc)
    add_demographics(doc)
    add_validation(doc)
    add_statistics(doc)
    add_bias_register(doc)
    add_ethics(doc)
    add_implementation(doc)
    add_acceptance(doc)
    add_sources(doc)

    # Prevent headings stranded at page bottoms and keep rows expandable.
    for paragraph in doc.paragraphs:
        if paragraph.style.name.startswith("Heading"):
            paragraph.paragraph_format.keep_with_next = True
        paragraph.paragraph_format.widow_control = True
    for table in doc.tables:
        for row in table.rows:
            tr_pr = row._tr.get_or_add_trPr()
            cant_split = OxmlElement("w:cantSplit")
            tr_pr.append(cant_split)

    doc.save(OUT)
    print(OUT)


if __name__ == "__main__":
    build()
