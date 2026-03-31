"""
MediCore HMS — PDF Generation Service
Install: pip install reportlab
"""
import io
from datetime import datetime


def generate_prescription_pdf(rx_data, patient_data, hospital_data):
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.enums import TA_CENTER

        buf   = io.BytesIO()
        doc   = SimpleDocTemplate(buf, pagesize=A4,
                                   rightMargin=15*mm, leftMargin=15*mm,
                                   topMargin=12*mm, bottomMargin=12*mm)
        blue  = colors.HexColor('#1a6fc4')
        teal  = colors.HexColor('#0f9e75')
        gray  = colors.HexColor('#64748b')
        light = colors.HexColor('#f8fafc')
        story = []

        def sty(name, **kw):
            return ParagraphStyle(name, **kw)

        story += [
            Paragraph(hospital_data.get('name','MediCore Hospital'),
                      sty('H', fontSize=16, fontName='Helvetica-Bold', textColor=blue, alignment=TA_CENTER)),
            Paragraph(hospital_data.get('address',''),
                      sty('S', fontSize=8, fontName='Helvetica', textColor=gray, alignment=TA_CENTER)),
            HRFlowable(width='100%', thickness=1.5, color=blue, spaceBefore=4, spaceAfter=4),
            Paragraph('PRESCRIPTION',
                      sty('T', fontSize=12, fontName='Helvetica-Bold', textColor=blue, alignment=TA_CENTER)),
            Spacer(1, 4*mm),
        ]

        info = [
            ['Patient:', patient_data.get('full_name',''), 'Rx No.:', rx_data.get('prescription_no','')],
            ['UHID:', patient_data.get('uhid',''), 'Date:', rx_data.get('date','')],
            ['Age/Gender:', f"{patient_data.get('age','?')} / {str(patient_data.get('gender','')).capitalize()}", 'Doctor:', rx_data.get('doctor','')],
        ]
        it = Table(info, colWidths=[28*mm, 58*mm, 25*mm, 64*mm])
        it.setStyle(TableStyle([
            ('FONTNAME',  (0,0),(-1,-1),'Helvetica'),
            ('FONTNAME',  (0,0),(0,-1),'Helvetica-Bold'),
            ('FONTNAME',  (2,0),(2,-1),'Helvetica-Bold'),
            ('FONTSIZE',  (0,0),(-1,-1),8.5),
            ('TEXTCOLOR', (0,0),(0,-1),gray),
            ('TEXTCOLOR', (2,0),(2,-1),gray),
            ('BACKGROUND',(0,0),(-1,-1),light),
            ('ROWBACKGROUNDS',(0,0),(-1,-1),[light, colors.white]),
            ('GRID',      (0,0),(-1,-1),0.3,colors.HexColor('#e2e8f0')),
            ('PADDING',   (0,0),(-1,-1),4),
        ]))
        story.append(it)
        story.append(Spacer(1,4*mm))
        story.append(Paragraph('Medications',
                      sty('MH', fontSize=10, fontName='Helvetica-Bold', textColor=teal)))
        story.append(HRFlowable(width='100%', thickness=0.5, color=teal, spaceBefore=2, spaceAfter=3))

        rows = [['#','Medicine','Dosage','Frequency','Duration','Qty','Notes']]
        for i, d in enumerate(rx_data.get('drugs',[]), 1):
            rows.append([str(i), f"{d.get('name','')}", d.get('dosage',''),
                         d.get('frequency',''), d.get('duration',''),
                         str(d.get('quantity','')), d.get('instructions','')])
        mt = Table(rows, colWidths=[8*mm,42*mm,22*mm,25*mm,20*mm,10*mm,48*mm])
        mt.setStyle(TableStyle([
            ('BACKGROUND',  (0,0),(-1,0),blue),
            ('TEXTCOLOR',   (0,0),(-1,0),colors.white),
            ('FONTNAME',    (0,0),(-1,0),'Helvetica-Bold'),
            ('FONTNAME',    (0,1),(-1,-1),'Helvetica'),
            ('FONTSIZE',    (0,0),(-1,-1),8),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,light]),
            ('GRID',        (0,0),(-1,-1),0.3,colors.HexColor('#e2e8f0')),
            ('PADDING',     (0,0),(-1,-1),4),
            ('VALIGN',      (0,0),(-1,-1),'TOP'),
        ]))
        story.append(mt)
        if rx_data.get('notes'):
            story += [Spacer(1,3*mm),
                      Paragraph(f"Notes: {rx_data['notes']}",
                                sty('N', fontSize=8.5, fontName='Helvetica', textColor=gray))]
        story += [
            HRFlowable(width='100%', thickness=0.3, color=colors.HexColor('#e2e8f0'), spaceBefore=8, spaceAfter=3),
            Paragraph(f"Generated {datetime.now().strftime('%d %b %Y %H:%M')} | MediCore HMS | Computer-generated prescription",
                      sty('F', fontSize=7, fontName='Helvetica', textColor=gray, alignment=TA_CENTER))
        ]
        doc.build(story)
        buf.seek(0)
        return buf.getvalue()
    except Exception as e:
        return _minimal_pdf(f"Prescription {rx_data.get('prescription_no','')} | Error: {e}")


def generate_lab_report_pdf(report_data, patient_data, hospital_data):
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.enums import TA_CENTER

        buf   = io.BytesIO()
        doc   = SimpleDocTemplate(buf, pagesize=A4,
                                   rightMargin=15*mm, leftMargin=15*mm,
                                   topMargin=12*mm, bottomMargin=12*mm)
        blue  = colors.HexColor('#1a6fc4')
        teal  = colors.HexColor('#0f9e75')
        red   = colors.HexColor('#dc2626')
        gray  = colors.HexColor('#64748b')
        light = colors.HexColor('#f8fafc')

        def sty(name, **kw): return ParagraphStyle(name, **kw)

        story = [
            Paragraph(hospital_data.get('name','MediCore Hospital'),
                      sty('H', fontSize=16, fontName='Helvetica-Bold', textColor=blue, alignment=TA_CENTER)),
            Paragraph(hospital_data.get('address',''),
                      sty('S', fontSize=8, fontName='Helvetica', textColor=gray, alignment=TA_CENTER)),
            HRFlowable(width='100%', thickness=1.5, color=blue, spaceBefore=4, spaceAfter=4),
            Paragraph('LABORATORY REPORT',
                      sty('T', fontSize=12, fontName='Helvetica-Bold', textColor=blue, alignment=TA_CENTER)),
            Spacer(1, 4*mm),
        ]

        info = [
            ['Patient:', patient_data.get('full_name',''), 'Order No.:', report_data.get('order_no','')],
            ['UHID:', patient_data.get('uhid',''), 'Ordered:', report_data.get('ordered_at','')],
            ['Age/Gender:', f"{patient_data.get('age','?')} / {str(patient_data.get('gender','')).capitalize()}", 'Reported:', report_data.get('completed_at','')],
            ['Referred By:', report_data.get('doctor',''), 'Blood Group:', patient_data.get('blood_group','')],
        ]
        it = Table(info, colWidths=[28*mm, 58*mm, 25*mm, 64*mm])
        it.setStyle(TableStyle([
            ('FONTNAME',  (0,0),(-1,-1),'Helvetica'),
            ('FONTNAME',  (0,0),(0,-1),'Helvetica-Bold'),
            ('FONTNAME',  (2,0),(2,-1),'Helvetica-Bold'),
            ('FONTSIZE',  (0,0),(-1,-1),8.5),
            ('TEXTCOLOR', (0,0),(0,-1),gray),
            ('TEXTCOLOR', (2,0),(2,-1),gray),
            ('ROWBACKGROUNDS',(0,0),(-1,-1),[light, colors.white]),
            ('GRID',      (0,0),(-1,-1),0.3,colors.HexColor('#e2e8f0')),
            ('PADDING',   (0,0),(-1,-1),4),
        ]))
        story += [it, Spacer(1,4*mm),
                  Paragraph('Test Results', sty('RH', fontSize=10, fontName='Helvetica-Bold', textColor=teal)),
                  HRFlowable(width='100%', thickness=0.5, color=teal, spaceBefore=2, spaceAfter=3)]

        rows = [['Test Name','Result','Unit','Normal Range','Flag']]
        ts_extra = []
        for i, t in enumerate(report_data.get('tests',[]), 1):
            flag = t.get('flag','normal').upper()
            rows.append([t.get('name',''), t.get('result','—'), t.get('unit',''),
                         t.get('normal',''), '⚠ CRITICAL' if t.get('critical') else flag])
            if t.get('critical'):
                ts_extra += [('BACKGROUND',(0,i),(-1,i),colors.HexColor('#fef2f2')),
                              ('TEXTCOLOR', (4,i),(4,i),red)]
            elif flag not in ('NORMAL',''):
                ts_extra.append(('TEXTCOLOR',(4,i),(4,i),colors.HexColor('#b45309')))

        rt = Table(rows, colWidths=[55*mm, 28*mm, 20*mm, 42*mm, 30*mm])
        base_ts = [
            ('BACKGROUND',  (0,0),(-1,0), blue),
            ('TEXTCOLOR',   (0,0),(-1,0), colors.white),
            ('FONTNAME',    (0,0),(-1,0), 'Helvetica-Bold'),
            ('FONTNAME',    (0,1),(-1,-1),'Helvetica'),
            ('FONTSIZE',    (0,0),(-1,-1), 8),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white, light]),
            ('GRID',        (0,0),(-1,-1), 0.3, colors.HexColor('#e2e8f0')),
            ('PADDING',     (0,0),(-1,-1), 5),
        ] + ts_extra
        rt.setStyle(TableStyle(base_ts))
        story += [rt, Spacer(1,3*mm),
                  Paragraph('H=High  L=Low  ⚠=Critical values reported to physician',
                             sty('Leg', fontSize=7.5, fontName='Helvetica', textColor=gray)),
                  HRFlowable(width='100%', thickness=0.3, color=colors.HexColor('#e2e8f0'), spaceBefore=6, spaceAfter=3),
                  Paragraph(f"Generated {datetime.now().strftime('%d %b %Y %H:%M')} | MediCore HMS | Verified by Lab Technician",
                             sty('F', fontSize=7, fontName='Helvetica', textColor=gray, alignment=TA_CENTER))]

        doc.build(story)
        buf.seek(0)
        return buf.getvalue()
    except Exception as e:
        return _minimal_pdf(f"Lab Report {report_data.get('order_no','')} | Error: {e}")


def _minimal_pdf(msg):
    content = (b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
               b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
               b"3 0 obj<</Type/Page/Parent 2 0 R/Resources<</Font<</F1 4 0 R>>>>"
               b"/MediaBox[0 0 595 842]/Contents 5 0 R>>endobj\n"
               b"4 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
               b"5 0 obj<</Length 80>>\nstream\n"
               b"BT /F1 12 Tf 50 750 Td (" + msg[:80].encode() + b") Tj ET\nendstream\nendobj\n"
               b"xref\n0 6\n0000000000 65535 f \n"
               b"trailer<</Size 6/Root 1 0 R>>\nstartxref 0\n%%EOF")
    return content
