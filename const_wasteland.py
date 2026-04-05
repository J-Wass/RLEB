# gpt generating mapping of timezones codes to their UTC offset
timezone_offsets = {
    # UTC and GMT
    "UTC": "+0000",
    "GMT": "+0000",  # Coordinated Universal Time / Greenwich Mean Time
    # North American Time Zones
    "EST": "-0500",
    "EDT": "-0400",  # Eastern Standard Time / Eastern Daylight Time
    "CST": "-0600",
    "CDT": "-0500",  # Central Standard Time / Central Daylight Time
    "MST": "-0700",
    "MDT": "-0600",  # Mountain Standard Time / Mountain Daylight Time
    "PST": "-0800",
    "PDT": "-0700",  # Pacific Standard Time / Pacific Daylight Time
    "AKST": "-0900",
    "AKDT": "-0800",  # Alaska Standard Time / Alaska Daylight Time
    "HST": "-1000",
    "HAST": "-1000",
    "HADT": "-0900",  # Hawaii Standard Time / Hawaii Daylight Time
    # European Time Zones
    "CET": "+0100",
    "CEST": "+0200",  # Central European Time / Central European Summer Time
    "EET": "+0200",
    "EEST": "+0300",  # Eastern European Time / Eastern European Summer Time
    "WET": "+0000",
    "WEST": "+0100",  # Western European Time / Western European Summer Time
    "BST": "+0100",  # British Summer Time (Daylight saving time in the UK)
    # Russia Time Zones
    "MSK": "+0300",
    "MSD": "+0400",  # Moscow Standard Time / Moscow Daylight Time
    # Middle East
    "AST": "+0300",  # Arabia Standard Time
    "IRST": "+0330",
    "IRDT": "+0430", # Iran Standard Time / Iran Daylight Time
    "GST": "+0400",  # Gulf Standard Time
    "PKT": "+0500",  # Pakistan Standard Time
    # Asia-Pacific Time Zones
    "IST": "+0530",  # Indian Standard Time
    "BST": "+0600",  # Bangladesh Standard Time
    "ICT": "+0700",  # Indochina Time
    "WIB": "+0700",
    "WITA": "+0800",
    "WIT": "+0900",  # Indonesia Time Zones
    "CST": "+0800",  # China Standard Time
    "SGT": "+0800",  # Singapore Time
    "HKT": "+0800",  # Hong Kong Time
    "JST": "+0900",  # Japan Standard Time
    "KST": "+0900",  # Korea Standard Time
    "ACST": "+0930",
    "ACDT": "+1030",  # Australian Central Standard Time / Australian Central Daylight Time
    "AEST": "+1000",
    "AEDT": "+1100",  # Australian Eastern Standard Time / Australian Eastern Daylight Time
    "AWST": "+0800",  # Australian Western Standard Time
    "NZST": "+1200",
    "NZDT": "+1300",  # New Zealand Standard Time / New Zealand Daylight Time
    # Africa Time Zones
    "CAT": "+0200",  # Central Africa Time
    "EAT": "+0300",  # East Africa Time
    "SAST": "+0200",  # South Africa Standard Time
    "WAT": "+0100",  # West Africa Time
    # South American Time Zones
    "ART": "-0300",  # Argentina Time
    "BRT": "-0300",
    "BRST": "-0200",  # Brazil Standard Time / Brazil Summer Time
    "CLT": "-0400",
    "CLST": "-0300",  # Chile Standard Time / Chile Summer Time
    "PYT": "-0400",
    "PYST": "-0300",  # Paraguay Time / Paraguay Summer Time
    # Atlantic and Other Islands
    "AZOT": "-0100",
    "AZOST": "+0000",  # Azores Standard Time / Azores Summer Time
    "CVT": "-0100",  # Cape Verde Time
    "FNT": "-0200",  # Fernando de Noronha Time
    # Antarctica
    "NZST": "+1200",
    "NZDT": "+1300",  # Antarctica time zones similar to New Zealand
    "ROTT": "-0300",  # Rothera Research Station Time (Antarctica)
    # Other Common Time Zones
    "CHAST": "+1245",
    "CHADT": "+1345",  # Chatham Islands Standard Time / Daylight Time
    "NST": "-0330",
    "NDT": "-0230",  # Newfoundland Standard Time / Daylight Time
    "AFT": "+0430",  # Afghanistan Time
    "MST": "+0630",  # Myanmar Standard Time
    "CXT": "+0700",  # Christmas Island Time
    "VUT": "+1100",  # Vanuatu Time
    "SST": "-1100",  # Samoa Standard Time
    "CHST": "+1000",  # Chamorro Standard Time

    # Reddit sometimes sends values in UTC time, which we can just dump here
    "C-1200": "-1200",
    "C-1100": "-1100",
    "C-1000": "-1000",
    "C-0930": "-0930",
    "C-0900": "-0900",
    "C-0800": "-0800",
    "C-0700": "-0700",
    "C-0600": "-0600",
    "C-0500": "-0500",
    "C-0400": "-0400",
    "C-0330": "-0330",
    "C-0300": "-0300",
    "C-0230": "-0230",
    "C-0200": "-0200",
    "C-0100": "-0100",
    "C+0000": "+0000",
    "C+0100": "+0100",
    "C+0200": "+0200",
    "C+0300": "+0300",
    "C+0330": "+0330",
    "C+0400": "+0400",
    "C+0430": "+0430",
    "C+0500": "+0500",
    "C+0530": "+0530",
    "C+0545": "+0545",
    "C+0600": "+0600",
    "C+0630": "+0630",
    "C+0700": "+0700",
    "C+0800": "+0800",
    "C+0900": "+0900",
    "C+0930": "+0930",
    "C+1000": "+1000",
    "C+1030": "+1030",
    "C+1100": "+1100",
    "C+1200": "+1200",
    "C+1245": "+1245",
    "C+1300": "+1300",
    "C+1345": "+1345",
    "C+1400": "+1400",
}
