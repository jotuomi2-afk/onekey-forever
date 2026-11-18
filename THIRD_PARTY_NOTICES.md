# Third-party notices

## pfQuest data

`OneKeyDruid/QuestData.lua` is extracted (by `tools/extract_questdb.py`) from
the quest, NPC, object and item database of pfQuest, as packaged in the
Polestar addon's `Polestar_QuestDB`.

    pfQuest — https://github.com/shagu/pfQuest
    MIT License
    Copyright (c) 2017-2021 Eric Mauser (Shagu)

    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in all
    copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
    SOFTWARE.

**Open licensing question (blocks a public release, see docs/RELEASE.md).**
Polestar's `LICENSE-DATA.txt` says its pack mixes several sources: pfQuest
(MIT), but also QuestieDB facts (no licence file; the maintainers ask that it
be treated as all rights reserved), quest XP from web databases, and tables
read from the Blizzard game client. The current `QuestData.lua` was extracted
from that mixed pack, so it may carry more than pfQuest's MIT data. Before
publishing, rebuild it from pfQuest's own repository (MIT only), or leave the
quest hints out of the public package.

World of Warcraft is a trademark of Blizzard Entertainment. This project is
not affiliated with or endorsed by Blizzard.
