from io import BytesIO


def generate_pdf(template_html):
    try:
        from xhtml2pdf import pisa
        pdf = BytesIO()
        pisa_status = pisa.CreatePDF(
            template_html,
            dest=pdf
        )
        if pisa_status.err:
            return None
        return pdf
    except Exception as e:
        print("PDF generation error:", str(e))
        return None