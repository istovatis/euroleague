"""The PARQUET logo mark, shared by render_cards.py and render_brand.py."""


def centre_disc(color, size=None, uid="c"):
    """Centre-court badge: a solid disc with the halfway line and the centre circle cut
    out (transparent), so it works on any background. The line ends at the disc edge;
    with free ends the mark reads as the Greek letter phi."""
    dim = f' width="{size}" height="{size}"' if size else ""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"{dim}>
  <mask id="{uid}"><rect width="100" height="100" fill="#fff"/>
    <g fill="none" stroke="#000" stroke-width="9">
      <line x1="50" y1="0" x2="50" y2="100"/><circle cx="50" cy="50" r="20"/>
    </g></mask>
  <circle cx="50" cy="50" r="48" fill="{color}" mask="url(#{uid})"/>
</svg>"""
