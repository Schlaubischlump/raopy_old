"""
Wrapper classes to support easy handling of DMAP data.
See: https://github.com/tchapi/shairport-sync-ui/blob/master/DMAP_DAAP_Codes.md
"""
from struct import pack

from ..util import to_bytes, to_hex

DMAP_CODES =  {
    # media / technical
    'authenticationmethod': ('msau', 1),
    'authenticationschemes': ('msas', 5),
    'bag': ('mbcl', 12),
    'container': ('mcon', 12),
    'containercount': ('mctc', 5),
    'containeritemid': ('mcti', 5),
    'contentcodesname': ('mcna', 9),
    'contentcodesnumber': ('mcnm', 5),
    'contentcodesresponse': ('mccr', 12),
    'contentcodestype': ('mcty', 3),
    'databasescount': ('msdc', 5),
    'deletedid': ('mudl', 12),
    'dictionary': ('mdcl', 12),
    'editcommandssupported': ('meds', 5),
    'haschildcontainers': ('f?ch', 1),
    'itemcount': ('mimc', 5),
    'itemid': ('miid', 5),
    'itemkind': ('mikd', 7),
    'itemname': ('minm', 9),
    'listing': ('mlcl', 12),
    'listingitem': ('mlit', 12),
    'loginrequired': ('mslr', 1),
    'loginresponse': ('mlog', 12),
    'parentcontainerid': ('mpco', 5),
    'persistentid': ('mper', 9),
    'mediaprotocolversion': ('mpro', 11),
    'returnedcount': ('mrco', 5),
    'serverinforesponse': ('msrv', 12),
    'serverrevision': ('musr', 5),
    'sessionid': ('mlid', 5),
    'specifiedtotalcount': ('mtco', 5),
    'status': ('mstt', 5),
    'statusstring': ('msts', 9),
    'supportsautologout': ('msal', 1),
    'supportsbrowse': ('msbr', 1),
    'supportsextensions': ('msex', 1),
    'supportsindex': ('msix', 1),
    'supportspersistentids': ('mspi', 1),
    'supportsquery': ('msqy', 1),
    'supportsresolve': ('msrs', 1),
    'supportsupdate': ('msup', 1),
    'timeoutinterval': ('mstm', 5),
    'updateresponse': ('mupd', 12),
    'updatetype': ('muty', 1),
    'utcoffset': ('msto', 6),
    'utctime': ('mstc', 10),
    # track codes
    'apple': ('aePP', 1),
    'baseplaylist': ('abpl', 1),
    'bookmarkable': ('asbk', 1),
    'browsealbumlisting': ('abal', 12),
    'browseartistlisting': ('abar', 12),
    'browsecomposerlisting': ('abcp', 12),
    'browsegenrelisting': ('abgn', 12),
    'databasebrowse': ('abro', 12),
    'databaseplaylists': ('aply', 12),
    'databasesongs': ('adbs', 12),
    'playlistrepeatmode': ('aprm', 1),
    'playlistshufflemode': ('apsm', 1),
    'playlistsongs': ('apso', 12),
    'protocolversion': ('apro', 11),
    'resolve': ('arsv', 12),
    'resolveinfo': ('arif', 12),
    'serverdatabases': ('avdb', 12),
    'songalbum': ('asal', 9),
    'songalbumartist': ('asaa', 9),
    'songalbumid': ('asai', 7),
    'songartist': ('asar', 9),
    'songbeatsperminute': ('asbt', 3),
    'songbitrate': ('asbr', 3),
    'songbookmark': ('asbo', 5),
    'songcategory': ('asct', 9),
    'songcodecsubtype': ('ascs', 5),
    'songcodectype': ('ascd', 5),
    'songcomment': ('ascm', 9),
    'songcompilation': ('asco', 1),
    'songcomposer': ('ascp', 9),
    'songcontentdescription': ('ascn', 9),
    'songcontentrating': ('ascr', 1),
    'songdatakind': ('asdk', 1),
    'songdataurl': ('asul', 9),
    'songdateadded': ('asda', 10),
    'songdatemodified': ('asdm', 10),
    'songdatepurchased': ('asdp', 10),
    'songdatereleased': ('asdr', 10),
    'songdescription': ('asdt', 9),
    'songdisabled': ('asdb', 1),
    'songdisccount': ('asdc', 3),
    'songdiscnumber': ('asdn', 3),
    'songeqpreset': ('aseq', 9),
    'songextradata': ('ased', '" '),
    'songformat': ('asfm', 9),
    'songgapless': ('asgp', 1),
    'songgenre': ('asgn', 9),
    'songgrouping': ('agrp', 9),
    'songhasbeenplayed': ('ashp', 1),
    'songkeywords': ('asky', 9),
    'songlongcontentdescription': ('aslc', 9),
    'songlongsize': ('asls', 7),
    'songpodcasturl': ('aspu', 9),
    'songrelativevolume': ('asrv', 2),
    'songsamplerate': ('assr', 5),
    'songsize': ('assz', 5),
    'songstarttime': ('asst', 5),
    'songstoptime': ('assp', 5),
    'songtime': ('astm', 5),
    'songtrackcount': ('astc', 3),
    'songtracknumber': ('astn', 3),
    'songuserrating': ('asur', 1),
    'songyear': ('asyr', 3),
    'sortalbum': ('assu', 9),
    'sortalbumartist': ('assl', 9),
    'sortartist': ('assa', 9),
    'sortcomposer': ('assc', 9),
    'sortname': ('assn', 9),
    'sortseriesname': ('asss', 9),
    'supportsextradata': ('ated', 3),
    # itunes codes
    'adam_ids_array': ('aeAD', 12),
    'content_rating': ('aeCR', 9),
    'drm_key1_id': ('aeK1', 7),
    'drm_key2_id': ('aeK2', 7),
    'drm_platform_id': ('aeDP', 5),
    'drm_user_id': ('aeDR', 7),
    'drm_versions': ('aeDV', 5),
    'episode_num_str': ('aeEN', 9),
    'episode_sort': ('aeES', 5),
    'extended_media_kind': ('aeMk', 5),
    'gapless_dur': ('aeGU', 7),
    'gapless_enc_del': ('aeGE', 5),
    'gapless_enc_dr': ('aeGD', 5),
    'gapless_heur': ('aeGH', 5),
    'gapless_resy': ('aeGR', 7),
    'has_video': ('aeHV', 1),
    'is_hd_video': ('aeHD', 1),
    'is_podcast': ('aePC', 1),
    'itms_artistid': ('aeAI', 5),
    'itms_composerid': ('aeCI', 5),
    'itms_genreid': ('aeGI', 5),
    'itms_playlistid': ('aePI', 5),
    'itms_songid': ('aeSI', 5),
    'itms_storefrontid': ('aeSF', 5),
    'mediakind': ('aeMK', 1),
    'music_sharing_version': ('aeSV', 5),
    'network_name': ('aeNN', 9),
    'non_drm_user_id': ('aeND', 7),
    'norm_volume': ('aeNV', 5),
    'req_fplay': ('????', 1),
    'saved_genius': ('aeSG', 1),
    'season_num': ('aeSU', 5),
    'series_name': ('aeSN', 9),
    'smart_playlist': ('aeSP', 1),
    'special_playlist': ('aePS', 1),
    'store_pers_id': ('aeSE', 7),
    'xid': ('aeXD', 9),
    # jukebox
    'jukebox_client_vote': ('ceJC', 2),
    'jukebox_current': ('ceJI', 5),
    'jukebox_score': ('ceJS', 4),
    'jukebox_vote': ('ceJV', 5)
 }


class DmapItem(object):
    """
    Class to represent a single Dmap item.
    """
    __slots__ = ["value", "ctype", "code"]

    def __init__(self, **kwargs):
        """
        This constructor excepts only kwargs of length 1 !
        :param kwargs: {dmap descriptor : value}
        """
        super(DmapItem, self).__init__()

        if len(kwargs) != 1:
            raise ValueError("Dmap item consists of only one entry.")

        descriptor = list(kwargs.keys())[0]

        if not descriptor in DMAP_CODES:
            raise ValueError("{0} is not a valid dmap entry.".format(descriptor))

        self.value = kwargs[descriptor]
        self.code, self.ctype = DMAP_CODES[descriptor]

    def to_data(self):
        """
        Pack the dmap code to binary data.

        | type | name      | description                                                                         |
        |------|-----------|-------------------------------------------------------------------------------------|
        | 1    | char      | 1-byte value, can be used as a boolean (true if the value is present, false if not) |
        | 3    | short     | 2-byte integer                                                                      |
        | 5    | long      | 4-byte integer                                                                      |
        | 7    | long long | 8-byte integer, tends to be represented in hex rather than numerical form           |
        | 9    | string    | string of characters (UTF-8)                                                        |
        | 10   | date      | 4-byte integer with seconds since 1970 (standard UNIX time format)                  |
        | 11   | version   | 2-bytes major version, next byte minor version, last byte patchlevel                |
        | 12   | container | contains a series of other chunks, one after the other                              |

        :return: binary data
        """
        c1, c2, c3, c4 = [ord(c) for c in self.code]

        fmt = ">BBBBI"
        size = 0
        if self.ctype == 1:
            fmt += "c"
            size = 1
        elif self.ctype == 3:
            fmt += "h"
            size = 2
        elif self.ctype == 5:
            fmt += "l"
            size = 4
        elif self.ctype == 7:
            fmt += "q"
            size = 8
        elif self.ctype == 10:
            fmt += "l"
            size = 4
        else:
            # we don't know how to handle the data... let's append it and hope the best
            return pack(fmt, c1, c2, c3, c4, len(self.value)) + to_bytes(self.value)

        return pack(fmt, c1, c2, c3, c4, size, self.value)


class DmapList(DmapItem):
    """
    Class to represent a `mlit` DmapItem
    """
    __slots__ = ["items"]

    def __init__(self, **kwargs):
        self.items = [DmapItem(**{des: val}) for des, val in kwargs.items()]
        daap_data = b"".join(item.to_data() for item in self.items)

        super(DmapList, self).__init__(listingitem=daap_data)
