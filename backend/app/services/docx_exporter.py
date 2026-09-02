import io
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn, nsdecls

class DocxExporter:
    """
    Native Word (.docx) Redline Export Engine.
    Generates professional contract redlines with strikethrough red original text,
    green underlined counter-language, and callout boxes for risk explanations.
    """

    @staticmethod
    def _set_cell_background(cell, fill_hex: str):
        shading_elm = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
        cell._tc.get_or_add_tcPr().append(shading_elm)

    @classmethod
    def generate_redline_docx(cls, report_data: dict) -> io.BytesIO:
        doc = Document()

        # Document Title
        title_p = doc.add_paragraph()
        title_run = title_p.add_run("TraceClause AI — Contract Redline Report")
        title_run.font.name = "Arial"
        title_run.font.size = Pt(22)
        title_run.font.bold = True
        title_run.font.color.rgb = RGBColor(15, 23, 42) # Slate 900
        title_p.alignment = WD_ALIGN_PARAGRAPH.LEFT

        # Metadata Header Table / Paragraph
        file_name = report_data.get("file_name", "Contract Audit Report")
        risk_score = report_data.get("overall_risk_score", "MEDIUM").upper()

        meta_p = doc.add_paragraph()
        meta_p.paragraph_format.space_after = Pt(14)
        
        r1 = meta_p.add_run(f"Document File: ")
        r1.bold = True
        meta_p.add_run(f"{file_name}\n")
        
        r2 = meta_p.add_run(f"Overall Risk Score: ")
        r2.bold = True
        
        risk_run = meta_p.add_run(f"{risk_score}\n")
        risk_run.bold = True
        if "HIGH" in risk_score:
            risk_run.font.color.rgb = RGBColor(225, 29, 72) # Red
        elif "LOW" in risk_score:
            risk_run.font.color.rgb = RGBColor(22, 163, 74) # Green
        else:
            risk_run.font.color.rgb = RGBColor(217, 119, 6) # Amber

        # Summary Section
        summary_json = report_data.get("summary_json", {})
        if isinstance(summary_json, str):
            import json
            try:
                summary_json = json.loads(summary_json)
            except Exception:
                summary_json = {"executive_summary": summary_json}

        exec_summary = summary_json.get("executive_summary", "") if isinstance(summary_json, dict) else str(summary_json)
        if exec_summary:
            h2 = doc.add_heading("Executive Risk Summary", level=2)
            h2.runs[0].font.color.rgb = RGBColor(30, 41, 59)
            
            p = doc.add_paragraph(exec_summary)
            p.paragraph_format.space_after = Pt(16)

        # Clauses & Redlines Section
        doc.add_heading("Clause-by-Clause Redline Analysis", level=2)

        clauses = report_data.get("clauses_json", [])
        if isinstance(clauses, str):
            import json
            try:
                clauses = json.loads(clauses)
            except Exception:
                clauses = []

        for idx, clause in enumerate(clauses, start=1):
            c_num = clause.get("clause_number", idx)
            c_title = clause.get("title", f"Clause {c_num}")
            original_text = clause.get("original_text", clause.get("clause_text", ""))
            risk_level = clause.get("risk_level", "LOW").upper()
            explanation = clause.get("explanation", clause.get("summary", ""))
            counter_lang = clause.get("counter_language", clause.get("recommended_fix", ""))

            # Clause Subheading
            c_head = doc.add_paragraph()
            c_head.paragraph_format.space_before = Pt(14)
            c_head.paragraph_format.space_after = Pt(4)
            
            c_head_run = c_head.add_run(f"Clause {c_num}: {c_title}  ")
            c_head_run.bold = True
            c_head_run.font.size = Pt(13)

            c_badge = c_head.add_run(f"[{risk_level} RISK]")
            c_badge.bold = True
            c_badge.font.size = Pt(10)
            if risk_level == "HIGH":
                c_badge.font.color.rgb = RGBColor(225, 29, 72)
            elif risk_level == "MEDIUM":
                c_badge.font.color.rgb = RGBColor(217, 119, 6)
            else:
                c_badge.font.color.rgb = RGBColor(22, 163, 74)

            # Redline Text Block
            redline_p = doc.add_paragraph()
            redline_p.paragraph_format.space_after = Pt(6)

            if counter_lang and counter_lang.strip():
                # Strikethrough Original (Red)
                orig_run = redline_p.add_run(original_text + " ")
                orig_run.font.strike = True
                orig_run.font.color.rgb = RGBColor(225, 29, 72) # Red strikethrough

                # Underlined Counter-Language (Green)
                fix_run = redline_p.add_run("\nSuggested Redline: " + counter_lang)
                fix_run.font.underline = True
                fix_run.font.bold = True
                fix_run.font.color.rgb = RGBColor(22, 163, 74) # Green underline
            else:
                norm_run = redline_p.add_run(original_text)
                norm_run.font.color.rgb = RGBColor(51, 65, 85)

            # Plain-English Explanation Callout Box
            if explanation:
                table = doc.add_table(rows=1, cols=1)
                table.alignment = WD_TABLE_ALIGNMENT.CENTER
                cell = table.cell(0, 0)
                cell.width = Inches(6.5)
                
                # Light callout fill
                if risk_level == "HIGH":
                    cls._set_cell_background(cell, "FFF1F2") # Light red
                elif risk_level == "MEDIUM":
                    cls._set_cell_background(cell, "FEF3C7") # Light amber
                else:
                    cls._set_cell_background(cell, "F0FDF4") # Light green

                cp = cell.paragraphs[0]
                cp.paragraph_format.space_before = Pt(4)
                cp.paragraph_format.space_after = Pt(4)
                
                c_label = cp.add_run("Risk Rationale & Legal Advice: ")
                c_label.bold = True
                c_label.font.size = Pt(10)
                
                c_exp = cp.add_run(explanation)
                c_exp.font.size = Pt(10)
                c_exp.font.italic = True

            doc.add_paragraph().paragraph_format.space_after = Pt(6)

        # Output Stream
        target_stream = io.BytesIO()
        doc.save(target_stream)
        target_stream.seek(0)
        return target_stream
