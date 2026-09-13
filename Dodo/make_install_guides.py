"""Tiny install-guide PDFs for Dodo Digital Files (the uploader requires a file)."""

from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

OUT = Path(__file__).resolve().parent
INK = HexColor("#1a2433")
SOFT = HexColor("#5b6b7c")
RULE = HexColor("#c5d4e4")
BAND = HexColor("#e8f1f8")

MAC_DRIVE = (
    "https://drive.google.com/file/d/1BTVMSQ6OCXOvIch8FsmO4FxIK4iSuKYE/view?usp=sharing"
)
WIN_DRIVE = (
    "https://drive.google.com/file/d/1L3UdbNhzzGyhEphri-nl4wHehDXTEQPu/view?usp=sharing"
)
LINK_BLUE = HexColor("#1a6bb5")


def drive_link(url: str, label: str) -> str:
    return f'<link href="{url}" color="blue"><u>{label}</u></link>'


GUIDES = [
    {
        "filename": "EyesRhythm-macOS-how-to-install.pdf",
        "title": "EyesRhythm for macOS",
        "subtitle": "How to install this copy",
        "steps": [
            "<b>This PDF is not the app.</b> It is only these steps. Your license key is in the same purchase email.",
            (
                "Download the Mac installer from Google Drive. Click "
                f"{drive_link(MAC_DRIVE, 'Download EyesRhythm for macOS')} "
                f"or paste this address into your browser:<br/>{drive_link(MAC_DRIVE, MAC_DRIVE)}<br/>"
                "Save <b>EyesRhythm-1.2.0.dmg</b> (this is the app, not a zip). If Google asks you to sign in, email hello@eyesrhythm.com."
            ),
            "Double-click the <b>.dmg</b>. Drag EyesRhythm into the <b>Applications</b> folder. Eject the disk image.",
            "Open Applications and double-click EyesRhythm. If macOS says it cannot be opened because it is from an unidentified developer: Control-click EyesRhythm → <b>Open</b> → <b>Open</b>. You only do this once.",
            "Paste the <b>license key</b> from this email and click <b>Activate</b>. Stay on Wi-Fi this once. After that, EyesRhythm stays on this computer.",
            "When macOS asks for the camera, click <b>Allow</b>. Later: System Settings → Privacy &amp; Security → Camera → EyesRhythm. Close Zoom, Teams, or any browser tab using the camera first.",
        ],
        "note": "This key is for macOS on one computer. It will not unlock the Windows copy.",
    },
    {
        "filename": "EyesRhythm-windows-how-to-install.pdf",
        "title": "EyesRhythm for Windows",
        "subtitle": "How to install this copy",
        "steps": [
            "<b>This PDF is not the app.</b> It is only these steps. Your license key is in the same purchase email.",
            (
                "Download the Windows installer from Google Drive. Click "
                f"{drive_link(WIN_DRIVE, 'Download EyesRhythm for Windows')} "
                f"or paste this address into your browser:<br/>{drive_link(WIN_DRIVE, WIN_DRIVE)}<br/>"
                "Save <b>EyesRhythm-Setup-1.2.0.exe</b> (this is the installer, not a zip). If Google asks you to sign in, email hello@eyesrhythm.com."
            ),
            "Right-click the <b>.exe</b> → Properties → tick <b>Unblock</b> → Apply, if Windows shows that box.",
            "Double-click the Setup file. You do not need an administrator account. If Windows shows “Windows protected your PC”: <b>More info</b> → <b>Run anyway</b>.",
            "Finish the installer. Open EyesRhythm from the Start menu. Paste the <b>license key</b> from this email and click <b>Activate</b>. Stay online this once. After that, EyesRhythm stays on this computer.",
            "When Windows asks for the camera, click <b>Allow</b>. Later: Settings → Privacy &amp; security → Camera → allow desktop apps, then allow EyesRhythm. Close Zoom, Teams, or any browser tab using the camera first.",
        ],
        "note": "This key is for Windows on one computer. It will not unlock the Mac copy.",
    },
]


def styles():
    base = getSampleStyleSheet()
    return {
        "kicker": ParagraphStyle(
            "kicker",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=SOFT,
            letterSpacing=0.6,
            spaceAfter=6,
        ),
        "title": ParagraphStyle(
            "title",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=26,
            textColor=INK,
            alignment=TA_LEFT,
            spaceAfter=4,
        ),
        "sub": ParagraphStyle(
            "sub",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=12,
            leading=16,
            textColor=SOFT,
            spaceAfter=16,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=10.5,
            leading=15,
            textColor=INK,
            linkColor=LINK_BLUE,
        ),
        "note": ParagraphStyle(
            "note",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=INK,
            spaceBefore=10,
        ),
        "foot": ParagraphStyle(
            "foot",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            textColor=SOFT,
            spaceBefore=8,
        ),
    }


def build(guide: dict) -> Path:
    path = OUT / guide["filename"]
    s = styles()
    doc = SimpleDocTemplate(
        str(path),
        pagesize=letter,
        leftMargin=0.85 * inch,
        rightMargin=0.85 * inch,
        topMargin=0.8 * inch,
        bottomMargin=0.75 * inch,
        title=guide["title"],
        author="EyesRhythm",
    )
    story = [
        Paragraph("EYESRHYTHM  ·  START HERE", s["kicker"]),
        Paragraph(guide["title"], s["title"]),
        Paragraph(guide["subtitle"], s["sub"]),
    ]
    for i, step in enumerate(guide["steps"], start=1):
        story.append(Paragraph(f"<b>{i}.</b>  {step}", s["body"]))
        story.append(Spacer(1, 10))
    story.extend(
        [
            Paragraph(guide["note"], s["note"]),
            Paragraph(
                "Need help? Email hello@eyesrhythm.com from the address you used at checkout. "
                'Camera setup: <link href="https://eyesrhythm.com/journal/camera-setup" color="blue">'
                "<u>https://eyesrhythm.com/journal/camera-setup</u></link>",
                s["foot"],
            ),
        ]
    )
    doc.build(story)
    return path


def main() -> None:
    for guide in GUIDES:
        path = build(guide)
        print(f"{path.name}  {path.stat().st_size} bytes")


if __name__ == "__main__":
    main()
