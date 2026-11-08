import sys
from functools import lru_cache
from http.client import HTTPException
from urllib.parse import parse_qsl, urlencode

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin

from playlist import load_playlist, plugin_id


ADDON = xbmcaddon.Addon()
LABEL = ADDON.getLocalizedString
PLAYLIST_ROOT = 'https://raw.githubusercontent.com/issouf-prog/michaz1988.github.io/main/'
PRESETS = {
    'tv': (30001, 'tv.m3u'),
    'tv-at': (30002, 'tv-at.m3u'),
    'tv2': (30003, 'tv2.m3u'),
}


@lru_cache(maxsize=None)
def has_addon(addon_id):
    return xbmc.getCondVisibility(f'System.HasAddon({addon_id})')


def add_folder(base, handle, label, action, **params):
    path = f'{base}?{urlencode(dict(action=action, **params))}'
    xbmcplugin.addDirectoryItem(handle, path, xbmcgui.ListItem(label), isFolder=True)


def show_channels(base, handle, channels):
    for channel in channels:
        dependency = plugin_id(channel.url)
        if dependency and not has_addon(dependency):
            add_folder(base, handle, LABEL(30009).format(channel.title), 'missing', addon=dependency)
            continue
        item = xbmcgui.ListItem(channel.title)
        item.setProperty('IsPlayable', 'true')
        if channel.logo:
            item.setArt({'thumb': channel.logo, 'icon': channel.logo})
        xbmcplugin.addDirectoryItem(handle, channel.url, item, isFolder=False)


def browse(base, handle, params):
    action = params.get('action', '')
    custom_url = ADDON.getSettingString('playlist_url').strip()
    if not action:
        for key, (label, _) in PRESETS.items():
            add_folder(base, handle, LABEL(label), 'playlist', source=key)
        if custom_url:
            add_folder(base, handle, LABEL(30004), 'playlist', source='custom')
        add_folder(base, handle, LABEL(30005), 'settings')
        return True
    if action == 'settings':
        ADDON.openSettings()
        return False
    if action == 'missing':
        xbmcgui.Dialog().ok(ADDON.getAddonInfo('name'), LABEL(30010).format(params.get('addon', '')))
        return False
    if action not in ('playlist', 'all', 'group', 'search'):
        return False

    source = params.get('source')
    if source == 'custom' and custom_url:
        url = custom_url
    elif source in PRESETS:
        url = PLAYLIST_ROOT + PRESETS[source][1]
    else:
        return False
    try:
        channels = load_playlist(url)
    except (HTTPException, OSError, ValueError):
        xbmcgui.Dialog().ok(ADDON.getAddonInfo('name'), LABEL(30011))
        return False
    if not channels:
        xbmcgui.Dialog().ok(ADDON.getAddonInfo('name'), LABEL(30012))
        return False

    if action == 'playlist':
        add_folder(base, handle, LABEL(30006), 'all', source=source)
        add_folder(base, handle, LABEL(30007), 'search', source=source)
        for group in sorted({channel.group for channel in channels}, key=str.casefold):
            add_folder(base, handle, group or LABEL(30008), 'group', source=source, group=group)
    else:
        if action == 'group':
            channels = [channel for channel in channels if channel.group == params.get('group')]
        elif action == 'search':
            query = xbmcgui.Dialog().input(LABEL(30007)).strip().casefold()
            if not query:
                return False
            channels = [channel for channel in channels if query in channel.title.casefold()]
            if not channels:
                xbmcgui.Dialog().ok(ADDON.getAddonInfo('name'), LABEL(30013))
                return False
        show_channels(base, handle, channels)
    return True


if __name__ == '__main__':
    handle = int(sys.argv[1])
    params = dict(parse_qsl(sys.argv[2].lstrip('?'), keep_blank_values=True))
    success = browse(sys.argv[0], handle, params)
    xbmcplugin.endOfDirectory(handle, succeeded=success, cacheToDisc=False)
    if params.get('action') == 'settings':
        xbmc.executebuiltin('Container.Refresh')
