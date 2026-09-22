"""Generic JasperViewer report bridge for BKPOS management/financial reports."""
from __future__ import annotations
from pathlib import Path
from datetime import datetime
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape
from .jasper_receipt import open_in_jasperviewer, REPORT_DIR, _uid

NS='http://jasperreports.sourceforge.net/jasperreports/print'
XSI='http://www.w3.org/2001/XMLSchema-instance'
XSD='http://jasperreports.sourceforge.net/xsd/jasperprint.xsd'

def open_table_report(title, columns, rows, summary=None, period=None, parent=None):
    """Create a readable A4 JasperPrint/JRPXML report from report-table data and open JasperViewer."""
    summary = summary or []
    rows = [tuple('' if v is None else str(v) for v in r) for r in rows]
    columns = [str(c) for c in columns]
    width, height, left = 595, 842, 36
    usable = width - 2*left
    line_h = 16
    pages=[]
    current=[]
    y=34
    def new_page():
        nonlocal current,y
        current=[]; pages.append(current); y=34
        add_header()
    def add_text(text,x,y,w,h=16,size=9,bold=False,align='Left'):
        node=('text',str(text),x,y,w,h,size,bold,align); current.append(node)
    def add_header():
        add_text(title,left,y,usable,26,16,True,'Center')
        yy=y+30
        if period:
            add_text(f'Period: {period}',left,yy,usable,16,8,False,'Center'); yy+=18
        add_text(f'Generated: {datetime.now():%Y-%m-%d %H:%M}',left,yy,usable,16,8,False,'Center')
    new_page(); y += 70
    if summary:
        add_text('SUMMARY',left,y,usable,18,10,True); y += 20
        for label,value in summary:
            add_text(f'{label}: {value}',left,y,usable,line_h,9,False); y += line_h
        y += 8
    # determine column widths from content, capped for readable A4 output
    n=max(1,len(columns)); raw=[max(8,min(28,len(c)+2)) for c in columns]
    for row in rows:
        for i,v in enumerate(row[:n]): raw[i]=max(raw[i],min(32,len(v)+2))
    total=sum(raw); widths=[usable*r/total for r in raw]
    def draw_row(values, header=False):
        nonlocal y
        if y > 790:
            new_page(); y += 70
        x=left
        for i,w in enumerate(widths):
            v=values[i] if i<len(values) else ''
            # wrap long cells into two visual lines without losing data excessively
            txt=v if len(v)<=42 else v[:39]+'...'
            add_text(txt,x,y,w,line_h,8,header,'Left'); x+=w
        y += line_h
    draw_row(columns,True)
    for row in rows: draw_row(row)
    root=ET.Element('jasperPrint',{'xmlns':NS,'xmlns:xsi':XSI,'xsi:schemaLocation':f'{NS} {XSD}',
        'name':str(title),'pageWidth':str(width),'pageHeight':str(height),
        'topMargin':'0','leftMargin':'0','bottomMargin':'0','rightMargin':'0','locale':'en_ZA'})
    ET.SubElement(root,'origin',{'band':'detail'})
    for name,size,bold in [('normal','9','false'),('small','8','false'),('bold','8','true'),('title','16','true')]:
        ET.SubElement(root,'style',{'name':name,'forecolor':'#111111','fontName':'SansSerif','fontSize':size,'isBold':bold})
    for p in pages:
        page=ET.SubElement(root,'page')
        for kind,text,x,yy,w,h,size,bold,align in p:
            style='title' if size>=16 else ('bold' if bold else 'small')
            node=ET.SubElement(page,'text',{'textAlignment':align,'textHeight':str(h-2),'lineSpacingFactor':'1.15','leadingOffset':'-1.5'})
            ET.SubElement(node,'reportElement',{'uuid':_uid(),'key':'report_text','style':style,'x':str(int(x)),'y':str(int(yy)),'width':str(int(w)),'height':str(int(h)),'origin':'0','srcId':'1'})
            content=ET.SubElement(node,'textContent'); content.text=escape(text)
    safe=''.join(c if c.isalnum() or c in '-_' else '_' for c in str(title))
    path=REPORT_DIR/f'mipos_report_{safe}_{datetime.now():%Y%m%d_%H%M%S}.jrpxml'
    path.write_bytes(ET.tostring(root,encoding='utf-8',xml_declaration=True))
    ok,msg=open_in_jasperviewer(path)
    if not ok: raise RuntimeError(msg)
    return path
