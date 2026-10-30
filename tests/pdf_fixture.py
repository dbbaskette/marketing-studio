"""Small selectable-text PDF generated entirely from synthetic test content."""
def source_pdf():
    words = b'BT /F1 12 Tf 72 720 Td (Synthetic PDF source for all studios.) Tj ET'
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>',
        b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>',
        b'<< /Length ' + str(len(words)).encode() + b' >>\nstream\n' + words + b'\nendstream',
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
    raw, offsets = b'%PDF-1.4\n', [0]
    for i, value in enumerate(objects, 1):
        offsets.append(len(raw)); raw += str(i).encode() + b' 0 obj\n' + value + b'\nendobj\n'
    at = len(raw)
    raw += b'xref\n0 6\n0000000000 65535 f \n'
    raw += b''.join(f'{offset:010d} 00000 n \n'.encode() for offset in offsets[1:])
    return raw + b'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n' + str(at).encode() + b'\n%%EOF\n'
