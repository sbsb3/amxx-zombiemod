// tsdiscordrelay.inc
// Shared helper so other TS plugins (rockthevote.sma, zombiemod-mysql.sma)
// can push events into the same Discord relay channel that
// discordbridge.sma owns, without any native/forward plumbing between
// plugins -- this is a `stock` function, so each including plugin gets its
// own compiled copy, and none of them ever touch discordbridge.sma itself.
//
// ts_discord_append() mirrors discordbridge.sma's private AppendFromTS()
// exactly: unix-timestamp prefix, one line per call, fields inside the
// message are '~'-joined by the caller (not by this helper), and the
// trailing newline is written via %c/10 in the same fprintf/vformat call --
// see discordbridge.sma's AppendFromTS() comment for why (other approaches
// produced corrupt output on this AMXX build).
//
// Canonical copy: gussven/tsdiscordrelay.inc
// Vendored copy:  amxx-zombiemod/tsdiscordrelay.inc (kept identical by hand;
//                 that plugin lives in its own git repo, so sync manually
//                 when this file changes)

#if defined _tsdiscordrelay_included
	#endinput
#endif
#define _tsdiscordrelay_included

#define DATA_DIR      "addons/amxmodx/data/discordbridge"
#define FROM_TS_FILE  "addons/amxmodx/data/discordbridge/fromts.txt"

// Append one event line to fromts.txt for ts_discord_relay.pl to pick up.
// eventFmt should already start with "<event>~field~field..." -- this just
// prefixes the unix timestamp and appends the line. Fails silently if
// fopen fails (e.g. discordbridge.sma hasn't created DATA_DIR yet).
stock ts_discord_append(const eventFmt[], any:...)
{
	new file = fopen(FROM_TS_FILE, "at");
	if (!file)
		return;

	new msg[512];
	vformat(msg, charsmax(msg), eventFmt, 2);

	fprintf(file, "%d %s%c", get_systime(), msg, 10);
	fclose(file);
}
