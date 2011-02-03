#!/usr/bin/env python

# Verification of BioNLP Shared Task - style annotations.

import sys
import os
import re
import argparse

import annotation
import annspec

# Issue types. Values should match with annotation interface.
AnnotationError = "AnnotationError"
AnnotationIncomplete = "AnnotationIncomplete"

class AnnotationIssue:
    """
    Represents an issue noted in verification of annotations.
    """

    _next_id_idx = 1

    def __init__(self, ann_id, type, description=""):
        self.id = "#%d" % AnnotationIssue._next_id_idx
        AnnotationIssue._next_id_idx += 1
        self.ann_id, self.type, self.description = ann_id, type, description
        if self.description is None:
            self.description = ""

    def __str__(self):
        return "%s\t%s %s\t%s" % (self.id, self.type, self.ann_id, self.description)

def argparser():
    ap=argparse.ArgumentParser(description="Verify BioNLP Shared Task annotations.")
    ap.add_argument("-v", "--verbose", default=False, action="store_true", help="Verbose output.")
    ap.add_argument("files", metavar="FILE", nargs="+", help="Files to verify.")
    return ap

def check_textbound_overlap(anns):
    """
    Checks for overlap between the given TextBoundAnnotations.
    Returns a list of pairs of overlapping annotations.
    """
    overlapping = []

    for a1 in anns:
        for a2 in anns:
            if a1 is a2:
                continue
            if a2.start < a1.end and a2.end > a1.start:
                overlapping.append((a1,a2))

    return overlapping

def contained_in_span(a1, a2):
    """
    Returns True if the first given TextBoundAnnotation is contained in the second, False otherwise.
    """
    return a1.start >= a2.start and a1.end <= a2.end

def verify_annotation(ann_obj):
    """
    Verifies the correctness of a given AnnotationFile.
    Returns a list of AnnotationIssues.
    """
    issues = []

    # TODO: break this up into separate functions.

    # check equivs
    for eq in ann_obj.get_equivs():
        # get the equivalent annotations
        equiv_anns = [ann_obj.get_ann_by_id(eid) for eid in eq.entities]

        # all the types of the Equivalent entities have to match
        eq_type = {}
        for e in equiv_anns:
            eq_type[e.type] = True
        if len(eq_type) != 1:
            # more than one type
            # TODO: mark this error on the Eq relation, not the entities
            for e in equiv_anns:
                issues.append(AnnotationIssue(e.id, AnnotationError, "%s in Equiv relation involving entities of more than one type (%s)" % (e.id, ", ".join(eq_type.keys()))))

    # check for overlap between physical entities
    physical_entities = [a for a in ann_obj.get_textbounds() if a.type in annspec.physical_entity_types]
    overlapping = check_textbound_overlap(physical_entities)
    for a1, a2 in overlapping:
        if a1.start == a2.start and a1.end == a2.end:
            issues.append(AnnotationIssue(a1.id, AnnotationError, "Error: %s has identical span with %s %s" % (a1.type, a2.type, a2.id)))            
        elif contained_in_span(a1, a2):
            if a1.type not in annspec.allowed_entity_nestings.get(a2.type, annspec.allowed_entity_nestings['default']):
                issues.append(AnnotationIssue(a1.id, AnnotationError, "Error: %s cannot be contained in %s (%s)" % (a1.type, a2.type, a2.id)))
        elif contained_in_span(a2, a1):
            if a2.type not in annspec.allowed_entity_nestings.get(a1.type, annspec.allowed_entity_nestings['default']):
                issues.append(AnnotationIssue(a1.id, AnnotationError, "Error: %s cannot contain %s (%s)" % (a1.type, a2.type, a2.id)))
        else:
            # crossing boundaries; never allowed for physical entities.
            issues.append(AnnotationIssue(a1.id, AnnotationError, "Error: entity has crossing span with %s" % a2.id))
    
    # TODO: generalize to other cases please

#     # group textbounds by type
#     textbounds_by_type = {}
#     for a in ann_obj.get_textbounds():
#         if a.type not in textbounds_by_type:
#             textbounds_by_type[a.type] = []
#         textbounds_by_type[a.type].append(a)
#
#     # check for overlap between textbounds that should not have any
#     for type in textbounds_by_type:
#         if type not in annspec.no_sametype_overlap_textbound_types:
#             # overlap OK
#             continue
#
#         overlapping = check_textbound_overlap(textbounds_by_type[type])
#
#         for a1, a2 in overlapping:
#             issues.append(AnnotationIssue(a1.id, AnnotationError, "Error: %s cannot overlap another entity (%s) of the same type" % (a1.type, a2.id)))

    def event_nonum_args(e):
        # returns event arguments without trailing numbers
        # (e.g. "Theme1" -> "Theme").
        nna = {}
        for arg, aid in e.args:
            m = re.match(r'^(.*?)\d*$', arg)
            if m:
                arg = m.group(1)
            if arg not in nna:
                nna[arg] = []
            nna[arg].append(aid)
        return nna

    # check for events missing mandatory arguments
    for e in ann_obj.get_events():
        found_nonum_args = event_nonum_args(e)
        # TODO: don't hard-code what Themes are required for
        if "Theme" not in found_nonum_args and e.type != "Process":
            issues.append(AnnotationIssue(e.id, AnnotationIncomplete, "Theme required for event"))

    # check for events with disallowed arguments
    for e in ann_obj.get_events():
        allowed = annspec.event_argument_types.get(e.type, annspec.event_argument_types["default"])
        eargs = event_nonum_args(e)
        for a in eargs:
            if a not in allowed:
                issues.append(AnnotationIssue(e.id, AnnotationError, "Error: %s cannot take a %s argument" % (e.type, a)))
            else:
                for rid in eargs[a]:
                    r = ann_obj.get_ann_by_id(rid)
                    if r.type not in allowed[a] and ('event' not in allowed[a] or not isinstance(r, annotation.EventAnnotation)):
                        issues.append(AnnotationIssue(e.id, AnnotationError, "Error: %s argument %s cannot be of type %s" % (e.type, a, r.type)))

    # check for events with disallowed argument counts
    for e in ann_obj.get_events():
        found_nonum_args = event_nonum_args(e)
        for a in found_nonum_args:
            # TODO: don't hard-code what multiple arguments are allowed for
            if len(found_nonum_args[a]) > 1 and not (e.type == "Binding" and a in ("Theme", "Site")):
                issues.append(AnnotationIssue(e.id, AnnotationError, "Error: %s cannot take multiple %s arguments" % (e.type, a)))
    
    return issues

def main(argv=None):
    if argv is None:
        argv = sys.argv
    arg = argparser().parse_args(argv[1:])

    print >> sys.stderr, "TODO: implement command-line invocation"

if __name__ == "__main__":
    sys.exit(main())
