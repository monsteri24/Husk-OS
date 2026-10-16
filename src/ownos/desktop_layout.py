"""Shell placement policy, independent of the compositor and GTK widgets."""
from ownos.config import validate


def layout(settings):
    settings = validate(settings)
    edge = 'TOP' if settings['taskbar_position'] == 'top' else 'BOTTOM'
    return dict(panel_anchors=(edge, 'LEFT', 'RIGHT'), popup_edge=edge,
                popup_margin=80, desktop_margin_top=84 if edge == 'TOP' else 22)
