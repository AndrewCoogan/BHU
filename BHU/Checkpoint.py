#https://github.com/mpavan/ediblepickle/blob/master/ediblepickle.py
# I want to be able to toggle if its on or not with it being in PROD.

import os
import pickle
import logging
from string import Template
from tempfile import gettempdir
import types

__author__ = 'pavan.mnssk@gmail.com'
# ^^^ original author, I only added the trivial flag.

def bhu_checkpoint(key=0, unpickler=pickle.load, pickler=pickle.dump, work_dir=gettempdir(), refresh=False, prod=False):
    """
    A utility decorator to save intermediate results of a function. It is the
    caller's responsibility to specify a key naming scheme such that the output of
    each function call with different arguments is stored in a separate file.
    :param key: The key to store the computed intermediate output of the decorated function.
        if key is a string, it is used directly as the name.
        if key is a string.Template object, you can specify your file-naming
            convention using the standard string.Template conventions. Since string.Template
            uses named substitutions, it can handle only keyword arguments. Therfore, in addition to
            the standard Template conventions, an additional feature is provided to help with non-keyword
            arguments.
            For instance if you have a function definition as f(m, n,
            arg3='myarg3',arg4='myarg4'). Say you want your key to be:
                n followed by an _ followed by 'text' followed by arg3 followed
                by a . followed by arg4.
            Let n = 3, arg3='out', arg4='txt', then you are interested in
            getting '3_textout.txt'.
            This is written as key=Template('{1}_text$arg3.$arg4')
            The filename is first generated by substituting the kwargs, i.e
            key_id.substitute(kwargs), this would give the string
            '{1}_textout.txt' as output. This is further processed by a call to
            format with args as the argument, where the second argument is
            picked (since counting starts from 0), and we get 3_textout.txt.
        if key is a callable function, it is called with the same arguments as
            that of the function, in a special format.
            key must be of the form lambda arg, kwarg: ... your definition. arg
            is an iterable containing the un-named arguments of the function,
            and kwarg is a dictionary containing the keyword arguments.
            For instance, the above example can be written as:
            key = lambda arg, kwarg: '%d_text%s.%s'.format(arg[1], kwarg['arg3'], kwarg['arg4'])
            Or one can define a function that takes the same arguments:
            def key_namer(args, kwargs):
                return '%d_text%s.%s'.format(arg[1], kwarg['arg3'], kwarg['arg4'])
            This way you can do complex argument processing and name generation.
    :param pickler: The function that loads the saved object and returns.
    This should ideally be of the same format as the one that is computed.
    However, in certain cases, it is enough as long as it provides the
    information necessary for the caller, even if it is not exactly same as the
    object returned by the function.
    :param unpickler: The function that saves the computed object into a file.
    :param work_dir: The location where the checkpoint files are stored.
    :param do_refresh: If enabled, this will not skip, effectively disabling the
    decoration @checkpoint.
    REFRESHING: One of the intended ways to use the refresh feature is as follows:
    Say you are checkpointing a function f1, f2; have a file or a place where you define refresh variables:
    defs.py:
    -------
    REFRESH_f1 = True
    REFRESH_f2 = os.environ['F2_REFRESH']   # can set this externally
    code.py:
    -------
    @checkpoint(..., refresh=REFRESH_f1)
    def f1(...):
        your code.
    @checkpoint(..., refresh=REFRESH_f2)
    def f2(...):
        your code.
    This way, you have control on what to refresh without modifying the code,
    by setting the defs either via input or by modifying defs.py.
    """

    def decorator(func):
        def wrapped(*args, **kwargs):
            if prod:
                return
            
            # If first arg is a string, use it directly.
            if isinstance(key, str):
                save_file = os.path.join(work_dir, key)
            elif isinstance(key, Template):
                save_file = os.path.join(work_dir, key.substitute(kwargs))
                save_file = save_file.format(*args)
            elif isinstance(key, types.FunctionType):
                save_file = os.path.join(work_dir, key(args, kwargs))
            else:
                logging.warn('Using 0-th argument as default.')
                save_file = os.path.join(work_dir, '{0}')
                save_file = save_file.format(args[key])

            logging.info('checkpoint@ %s' % save_file)

            # cache_file doesn't exist, run the function and save output in checkpoint.

            if isinstance(refresh, types.FunctionType):
                do_refresh = refresh()
            else:
                do_refresh = refresh

            if do_refresh or not os.path.exists(path=save_file):  # Otherwise compute it save it and return it.
                # If the program fails, don't checkpoint.
                try:
                    out = func(*args, **kwargs)
                except: # a blank raise re-raises the last exception.
                    raise
                else:  # If the program is successful, then go ahead and call the save function.
                    with open(save_file, 'wb') as f:
                        pickler(out, f)
                        return out
            # Otherwise, load the checkpoint file and send it.
            else:
                logging.info("Checkpoint exists. Loading from: %s" % save_file)
                with open(save_file, 'rb') as f:
                    return unpickler(f)
        return wrapped

    return decorator