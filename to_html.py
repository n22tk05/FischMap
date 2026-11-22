from pathlib import Path


def to_html(content: str, output_path: str = "index.html") -> str:
    html_content = f"""<!DOCTYPE html>
                        <html lang="vi">
                        <head>
                            <meta charset="UTF-8">
                            <meta name="viewport" content="width=device-width, initial-scale=1.0">
                            <title>Trang của tôi</title>
                        </head>
                        <body>
                        {content}
                        </body>
                        </html>
                    """

    path = Path(output_path)
    path.write_text(html_content, encoding="utf-8")
    return str(path.resolve())