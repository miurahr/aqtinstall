#!/usr/bin/env python3
#
# Copyright (C) 2018 Linus Jahn <lnj@kaidan.im>
# Copyright (C) 2019-2021 Hiroshi Miura <miurahr@linux.com>
# Copyright (C) 2020, Aurélien Gâteau
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import multiprocessing
import os
from logging import getLogger
from logging.handlers import QueueHandler, QueueListener

from aqt.helper import Settings


def setup_logging(args, env_key="LOG_CFG"):
    if args is not None and args.logging_conf is not None:
        Settings.load_logging_conf(args.logging_conf)
    else:
        config = os.getenv(env_key, None)
        if config is not None and os.path.exists(config):
            Settings.load_logging_conf(config)
        else:
            Settings.load_logging_conf()


class QueueListenerHandler(QueueHandler):
    def __init__(self):
        queue = multiprocessing.Queue(-1)
        super().__init__(queue)
        handlers = getLogger("aqt").handlers
        listener = QueueListener(queue, *handlers, respect_handler_level=False)
        listener.start()

    def emit(self, record):
        return super().emit(record)
