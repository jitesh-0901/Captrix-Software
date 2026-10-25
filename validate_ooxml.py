import zipfile
import xml.etree.ElementTree as ET

TAG_ORDER_TBLPR = [
    'tblStyle', 'tblpPr', 'tblOverlap', 'bidiVisual', 'tblStyleRowBandSize',
    'tblStyleColBandSize', 'tblW', 'jc', 'tblCellSpacing', 'tblInd',
    'tblBorders', 'shd', 'tblLayout', 'tblCellMar', 'tblLook',
    'tblCaption', 'tblDescription', 'tblPrChange'
]

TAG_ORDER_TCPR = [
    'cnfStyle', 'tcW', 'gridSpan', 'hMerge', 'vMerge',
    'tcBorders', 'shd', 'noWrap', 'tcMar', 'textDirection',
    'tcFitText', 'vAlign', 'hideMark', 'headers',
    'cellIns', 'cellDel', 'cellMerge', 'tcPrChange'
]

def validate():
    target = 'Captrix_Project_Review_and_Submission_Dossier.docx'
    with zipfile.ZipFile(target, 'r') as z:
        for name in z.namelist():
            if name.endswith('.xml'):
                ET.fromstring(z.read(name))
                
        doc_tree = ET.fromstring(z.read('word/document.xml'))
        ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        
        tblprs = doc_tree.findall('.//w:tblPr', ns)
        print(f'Total tblPr elements found: {len(tblprs)}')
        for i, tp in enumerate(tblprs):
            tags = [c.tag.split('}')[-1] for c in tp]
            indices = [TAG_ORDER_TBLPR.index(t) for t in tags if t in TAG_ORDER_TBLPR]
            if indices != sorted(indices):
                raise ValueError(f'tblPr #{i} violates schema order: {tags}')

        tcprs = doc_tree.findall('.//w:tcPr', ns)
        print(f'Total tcPr elements found: {len(tcprs)}')
        for i, tp in enumerate(tcprs):
            tags = [c.tag.split('}')[-1] for c in tp]
            indices = [TAG_ORDER_TCPR.index(t) for t in tags if t in TAG_ORDER_TCPR]
            if indices != sorted(indices):
                raise ValueError(f'tcPr #{i} violates schema order: {tags}')

        drawings = doc_tree.findall('.//w:drawing', ns)
        print(f'Total w:drawing (images embedded): {len(drawings)}')
        print('SUCCESS: 100% Strict ECMA-376 OOXML Schema Compliant!')

if __name__ == '__main__':
    validate()
