# -*- coding: utf-8; -*-
"""
Copyright (C) 2007-2013 Guake authors

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License as
published by the Free Software Foundation; either version 2 of the
License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
General Public License for more details.

You should have received a copy of the GNU General Public
License along with this program; if not, write to the
Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor,
Boston, MA 02110-1301 USA
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os

# pylint: disable=wrong-import-position,wrong-import-order,unused-import
from guake import gi
assert gi  # hack to "use" the import so pep8/pyflakes are happy

# from gi.repository import Gdk
from gi.repository import Gtk
# pylint: enable=wrong-import-position,wrong-import-order,unused-import


class GuakeWidget(object):

    # __filename__ should be set in a child class
    __filename__ = None

    def __new__(cls, *args, **kwargs):
        """Create application from glade .ui file;
        ApplicationWindow identifier in the ui-file should be equal to cls.__name__"""
        assert isinstance(cls.__filename__, str), "%s has invalid __filename__!" % cls
        datapath = kwargs.get("datapath", "./data")
        filename = os.path.join(datapath, "ui", cls.__filename__)
        builder = Gtk.Builder()
        builder.add_from_file(filename)
        instance = builder.get_object(cls.__name__)
        assert instance is not None, "Gtk widget %s not found!" % cls.__name__
        instance.__class__ = cls
        del builder
        return instance