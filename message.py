#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

'''
Server-to-client messaging-related functionality for
Brat Rapid Annotation Tool (brat)
'''

# TODO: make this minimal implmentation into a proper messaging
# interface

__pending_messages = []

def display_message(s, type='info', duration=3):
    global __pending_messages
    __pending_messages.append((s, type, duration))

def add_messages_to_json(json_dict):
    global __pending_messages

    # to avoid crowding the interface, combine messages with identical content
    msgcount = {}
    for m in __pending_messages:
        msgcount[m] = msgcount.get(m,0)+1

    merged_messages = []
    for m in __pending_messages:
        if m in msgcount:
            count = msgcount[m]
            del msgcount[m]
            s, t, r = m
            if count > 1:
                s = s + "<br/><b>[message repeated %d times]</b>"%count
            merged_messages.append((s,t,r))

    if 'messages' not in json_dict:
        json_dict['messages'] = []
    json_dict['messages'] += merged_messages
    __pending_messages = []
