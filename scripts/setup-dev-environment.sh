#!/usr/bin/env bash
#
# Copyright (C) 2024 Travis Wichert
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#

die() {
  exit 1
}

curl -sSf https://rye.astral.sh/get | RYE_INSTALL_OPTION="--yes" bash || die
echo 'source "$HOME/.rye/env"' >> ~/.bashrc || die
source "$HOME/.rye/env"
rye install ruff
rye install uv
rye sync
ruff check
