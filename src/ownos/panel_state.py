"""Select panel presentation from real foreign-toplevel state on its output."""


def panel_mode(entries, output_name=None, geometry=None, monitor_count=1):
    """Keep a different output's fullscreen window from hiding this panel.

    wl_output v4 names match GDK's monitor plug names. Older compositors can
    still be matched by their logical output rectangles. Without either
    identity, infer membership only when there is a single output.
    """
    mode = 'desktop'
    for entry in entries:
        if entry.get('minimized'):
            continue
        outputs = entry.get('outputs')
        if outputs is None:
            belongs = monitor_count == 1
        else:
            belongs = False
            for output in outputs:
                if output_name and output.get('name'):
                    match = output_name == output['name']
                else:
                    match = (geometry is not None and tuple(geometry) ==
                             tuple(output.get(key) for key in ('x', 'y', 'width', 'height')))
                belongs = belongs or match
        if not belongs:
            continue
        if entry.get('fullscreen'):
            return 'fullscreen'
        if entry.get('maximized'):
            mode = 'maximized'
    return mode
