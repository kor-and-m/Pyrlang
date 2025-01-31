# Copyright 2018, Erlang Solutions Ltd, and S2HC Sweden AB
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

""" A helper module to assist with gen:call-style message parsing and replying.
    A generic incoming message looks like ``{$gen_call, {From, Ref}, Message}``.

    .. warning::
        This is a low level utility module. For handling GenServer-style calls
        please consider inheriting your Process from
        :py:class:`~Pyrlang.gen_server.GenServer` and following the docs.
"""

from pyrlang.util import as_str
from term.atom import Atom
from term.pid import Pid
from term.reference import Reference


class GenBase:
    """ Base class for Gen messages, do not use directly. See
        ``GenIncomingMessage`` and ``GenIncomingCall``.
    """
    def __init__(self, sender: Pid, ref: Reference, node_name: str):
        self.node_name_ = node_name

        self.sender_ = sender  # type: Pid
        """ Where to send replies to. """

        self.ref_ = ref
        """ An unique ref generated by the caller. 
            A ``term.Reference`` object. 
        """

    def reply(self, local_pid: Pid, result):
        """ Reply with a gen:call result
        """
        from pyrlang.node import Node
        n = Node.all_nodes[self.node_name_]
        n.send(sender=local_pid,
               receiver=self.sender_,
               message=(self.ref_, result))

    def reply_exit(self, local_pid: Pid, reason):
        """ Reply to remote gen:call with EXIT message which causes reason to be
            re-raised as exit() on the caller side
            NOTE: The gen:call caller attempts to monitor the target first. If
                the monitor attempt fails, the exit here won't work
        """
        from pyrlang.node import Node

        reply = ('monitor_p_exit', local_pid, self.sender_, self.ref_, reason)
        n = Node.all_nodes[self.node_name_]
        n._dist_command(receiver_node=self.sender_.node_name_, message=reply)


class GenIncomingMessage(GenBase):
    """ A helper class which contains elements from a generic incoming
        ``gen_server`` message.
        For those situations when gen message is not a call, or is an incoming
        ``gen_server`` call.
    """
    def __init__(self, sender: Pid, ref: Reference, message, node_name: str):
        GenBase.__init__(self, sender=sender, ref=ref, node_name=node_name)
        self.message_ = message
        """ The last part of the incoming message, the payload. """

    def __str__(self):
        return "GenIncomingMessage(" + str(self.message_) + ")"


class GenIncomingCall(GenBase):
    """ A helper class which contains elements from the incoming
        ``gen:call`` RPC call message.
    """

    def __init__(self, mod: str, fun: str, args: list,
                 group_leader: Pid, sender: Pid, ref: Reference,
                 node_name: str):

        GenBase.__init__(self, sender=sender, ref=ref, node_name=node_name)
        self.mod_ = mod
        """ Module name as string (input can be binary, atom or str). """

        self.fun_ = fun
        """ Function name as string (input can be binary, atom or str). """

        self.args_ = args  # type: list
        """ Call arguments as a ``list`` """

        self.group_leader_ = group_leader
        """ Remote group leader pid, comes in as a part of message. """


def parse_gen_call(msg, node_name: str):
    """ Determine if msg is a gen:call message and create a
        :py:class:`~Pyrlang.gen.GenIncomingCall` object.

        .. note::
            Module and function parameters to ``rpc:call`` can be
            binary, ASCII strings or atoms.

        .. note::
            You do not need to import module in ``rpc:call``, it is done by Rex.

        :param node_name: Name of the current node, used to route replies back
            to the caller
        :param msg: An Erlang tuple hopefully starting with a '$gen_call'
        :return: str with error if msg wasn't a call message, otherwise
            constructs and returns a ``GenIncomingCall`` object.
    """
    # Incoming {$gen_call, {From, Ref}, {call, Mod, Fun, Args}}
    if type(msg) != tuple:  # ignore all non-tuple messages
        return "Only {tuple} messages allowed"

    # ignore tuples with non-atom 1st, ignore non-gen_call mesages
    if not isinstance(msg[0], Atom) or msg[0].text_ != '$gen_call':
        return "Only {$gen_call, _, _} messages allowed"

    (_, _sender_mref, _call_mfa_gl) = msg
    (msender, mref) = _sender_mref

    # TODO: Maybe also check first element to be an atom 'call'
    if len(_call_mfa_gl) != 5:
        return "Expecting a 5-tuple (with a 'call' atom)"

    (call, m, f, args, group_leader) = _call_mfa_gl

    return GenIncomingCall(mod=as_str(m),
                           fun=as_str(f),
                           args=args,
                           group_leader=group_leader,
                           sender=msender,  # pid of the sender
                           ref=mref,  # reference used in response
                           node_name=node_name)


def parse_gen_message(msg, node_name: str):
    """ Might be an 'is_auth' request which is not a call

        :return: string on error, otherwise a ``GenIncomingMessage`` object
    """
    # Incoming {$gen_call, {From, Ref}, Message}
    if type(msg) != tuple:  # ignore all non-tuple messages
        return "Only {tuple} messages allowed"

    # ignore tuples with non-atom 1st, ignore non-gen_call mesages
    if not isinstance(msg[0], Atom) or msg[0] != '$gen_call':
        return "Only {$gen_call, _, _} messages allowed"

    (_, _sender_mref, gcmsg) = msg
    (msender, mref) = _sender_mref

    return GenIncomingMessage(sender=msender,
                              ref=mref,
                              message=gcmsg,
                              node_name=node_name)


__all__ = ['GenIncomingCall', 'GenIncomingMessage',
           'parse_gen_call', 'parse_gen_message']
