# Source.Python Admin

## Introduction
Source.Python Admin is an open-source project that uses the [Source.Python](https://github.com/Source-Python-Dev-Team/Source.Python) framework to allow for easy Administration on Source-engine servers.

## Front Ends
Source.Python Admin lets you gain control to its features via multiple front ends.
The front ends are:
- **Command** Front End
- **Popup/Menu** Front End
- **MoTD** Front End
- **Web** Front End

Here's a table showing what front ends are currently supported by each included plugin:

Plugin | Command | Popup/Menu | MoTD | Web
------ | ------- | ---------- | ---- | ---
Communication Management | No | **Yes** | No | No
Kick/Ban | No | **Yes** | **Yes** | No
Life Management | **Yes** | **Yes** | **Yes** | No
Team Management | No | **Yes** | No | No
Tracking | **Yes** | **Yes** | No | No

### Command Front End
Command front end allows executing features through chat and client commands.
#### Syntax:
- `!spa <command and sub-commands>` - public chat command
- `/spa <command and sub-commands>` - private chat command
- `spa <command and sub-commands>` - client command

The difference between public and private chat commands is that the private one suppresses the command string, so that nobody receives a chat message containing it.
Client commands are run via player's game console.

Player-based features (those have some kind of a player target) can also be executed via command front end.
#### Syntax (`!spa`, `/spa` and `spa` prefixes are omitted here, but otherwise are required):
`<command and sub-commands> <player filter> <filter argument>`

Where *player filter* is one of the following:
- `name` - this filter targets player by their name; *filter argument* is required in this case.
- `steamid`, `steam` - this filter targets player by their SteamID; *filter argument* is required in this case.
- `index` - this filter targets player by their entity index; *filter argument* is required in this case.
- `@<built-in template filter>` - this filter targets player using one of the template player filters; *filter argument* is omitted in this case; *built-in template filter* is one of the following:
  - `me`, `self` - targets the command issuer.
  - `all` - targets all players on the server.
  - `bot` - targets all bots on the server (including GOTV/SourceTV).
  - `human` - targets all human players on the server; opposite to `bot`.
  - `dead` - targets all dead players on the server.
  - `alive` - targets all alive players on the server; opposite to `dead`.
  - `un` - targets all unassigned players (those who didn't select their team).
  - `spec` - targets all spectators.
  - `t` - targets all team #2 players (terrorists, rebels, RED team etc).
  - `ct` - targets all team #3 players (counter-terrorists, combines, BLU team etc).
  - depending on the game, additional team filters might be defined.
- `#<userid>` - this filter targets player by their UserID (as reported by the `status` console command); *filter argument* is omitted in this case; *userid* is the target's UserID.
- `!<inverted player filter>` - this filter targets all players, but only not those who would otherwise be targeted by *inverted player filter*; *filter argument* is passed to the inverted player filter.

#### Examples:
- `/spa slay @all` - slays all players on the server
- `/spa slay !@me` - slays all players except the player who issues the command
- `/spa resurrect name iPlayer` - resurrects the player whose name matches "iPlayer"

### Popup/Menu Front End
This front end provides access to the features via in-game radio menus.
The main menu can be accessed by either running `spa menu` command in game console or typing `!spa menu` or `/spa menu` in game chat.
To get this menu to show up, the client must have `admin.base` permission.

### MoTD Front End
This front end provides allows to administrate the server from the in-game MoTD screen, providing the most impressive experience with the interactive graphical interface.
Its main screen shows up after running `spa motd` in game console or typing `!spa motd` or `/spa motd` in game chat.
The admin must have `admin.base` permission to open the MoTD front end.

### Web Front End
Web front end is the only front end that allows admins to access Source.Python Admin features remotely, without even playing on the server.
All it requires is a web-browser, then the admin can sign in via Steam OpenID.
Web front end works in two modes: offline and online.

- **online** mode provides an access to the regular set of the features;
- **offline** mode works directly with the server database - this is useful, for example, for banning players even when the game server is offline.

The switching between online and offline modes is done automatically.
