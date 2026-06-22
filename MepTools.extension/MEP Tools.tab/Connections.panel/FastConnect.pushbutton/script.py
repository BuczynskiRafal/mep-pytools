# -*- coding: utf-8 -*-
"""Connects two picked MEP elements: aligns their geometry and creates the connection."""

__title__ = "Fast\nConnect"
__doc__ = "Connects two picked MEP elements: aligns their geometry and creates the connection."
__author__ = "Rafal Buczynski"

import math

from Autodesk.Revit.DB import (
    Domain,
    ConnectorType,
    ConnectorProfileType,
    MEPCurve,
    FamilyInstance,
    Line,
    XYZ,
    Transaction,
    ElementTransformUtils,
    IFailuresPreprocessor,
    FailureProcessingResult,
    FailureSeverity,
)
from Autodesk.Revit.UI.Selection import ObjectType, ISelectionFilter
from Autodesk.Revit.Exceptions import OperationCanceledException
from pyrevit import revit, forms, HOST_APP

from fast_connect import ConnectorDomain, ConnectorInfo, find_best_pair

SIZE_TOLERANCE_FEET = 1.0 / 304.8  # ~1 mm

doc = revit.doc
uidoc = revit.uidoc

DOMAIN_MAP = {
    Domain.DomainPiping: ConnectorDomain.PIPING,
    Domain.DomainHvac: ConnectorDomain.DUCTING,
    Domain.DomainElectrical: ConnectorDomain.ELECTRICAL,
    Domain.DomainCableTrayConduit: ConnectorDomain.CABLE_TRAY,
}


class MepConnectableFilter(ISelectionFilter):
    def AllowElement(self, element):
        return (isinstance(element, MEPCurve)
                or (isinstance(element, FamilyInstance) and element.MEPModel is not None))

    def AllowReference(self, reference, position):
        return False


def get_end_connectors(element):
    # MepConnectableFilter already guarantees a connectable MEP element.
    manager = (element.ConnectorManager if isinstance(element, MEPCurve)
               else element.MEPModel.ConnectorManager)
    return [c for c in manager.Connectors
            if c.ConnectorType == ConnectorType.End]


def get_free_connectors(element):
    return [c for c in get_end_connectors(element) if not c.IsConnected]


class MepConnectWarningSwallower(IFailuresPreprocessor):
    def PreprocessFailures(self, failures_accessor):
        for failure in failures_accessor.GetFailureMessages():
            if failure.GetSeverity() == FailureSeverity.Warning:
                failures_accessor.DeleteWarning(failure)
        return FailureProcessingResult.Continue


def _suppress_connected_move_dialog(sender, args):
    args.OverrideResult(1)  # 1 = affirmative/OK on Revit's warning dialogs


def to_info(connector, index):
    origin = connector.Origin
    size = None
    if connector.Shape == ConnectorProfileType.Round:
        size = connector.Radius * 2.0
    domain = DOMAIN_MAP.get(connector.Domain, ConnectorDomain.UNDEFINED)
    return ConnectorInfo(index, origin.X, origin.Y, origin.Z, domain, size)


def align_connectors(moving_id, source, target):
    """Rotate and move the moving element so its source connector coincides with
    the target connector and faces it head-on (the connector axes point at each other)."""
    source_dir = source.CoordinateSystem.BasisZ
    desired_dir = target.CoordinateSystem.BasisZ.Negate()

    angle = source_dir.AngleTo(desired_dir)
    if angle > 1e-9:
        if angle < math.pi - 1e-9:
            axis = source_dir.CrossProduct(desired_dir).Normalize()
        elif abs(source_dir.Z) < 0.9:
            axis = source_dir.CrossProduct(XYZ.BasisZ).Normalize()   # anti-parallel case
        else:
            axis = source_dir.CrossProduct(XYZ.BasisX).Normalize()

        # The axis passes through the connector origin, so that point does not move during rotation.
        rotation_axis = Line.CreateUnbound(source.Origin, axis)
        ElementTransformUtils.RotateElement(doc, moving_id, rotation_axis, angle)

    # The connector is live: after rotation its Origin is up to date. Now move it into place.
    translation = target.Origin.Subtract(source.Origin)
    if not translation.IsZeroLength():
        ElementTransformUtils.MoveElement(doc, moving_id, translation)


def pick_two_elements():
    """Pick the fixed (stays) and moving element, or None if the user cancels."""
    selection_filter = MepConnectableFilter()
    try:
        reference_fixed = uidoc.Selection.PickObject(
            ObjectType.Element, selection_filter, "Pick the first element (stays in place).")
        reference_moving = uidoc.Selection.PickObject(
            ObjectType.Element, selection_filter, "Pick the second element (will be moved).")
    except OperationCanceledException:
        return None
    return doc.GetElement(reference_fixed), doc.GetElement(reference_moving)


def choose_connector_pair(fixed_element, moving_element):
    """Return the closest compatible (source on moving, target on fixed) pair,
    or None after alerting the user why no pair was found."""
    free_fixed = get_free_connectors(fixed_element)
    free_moving = get_free_connectors(moving_element)
    if not free_fixed or not free_moving:
        forms.alert("At least one element has no free connectors.")
        return None

    infos_fixed = [to_info(c, i) for i, c in enumerate(free_fixed)]
    infos_moving = [to_info(c, i) for i, c in enumerate(free_moving)]

    match = find_best_pair(infos_fixed, infos_moving, SIZE_TOLERANCE_FEET)
    if match is None:
        forms.alert("No compatible connector pair found (different domain or size).")
        return None

    target = free_fixed[match[0].source_index]
    source = free_moving[match[1].source_index]
    return source, target


def connect(moving_id, source, target):
    """Align the moving element to the fixed connector and create the connection."""
    uiapp = HOST_APP.uiapp
    transaction = Transaction(doc, "Fast Connect MEP")
    transaction.Start()

    options = transaction.GetFailureHandlingOptions()
    options.SetFailuresPreprocessor(MepConnectWarningSwallower())
    transaction.SetFailureHandlingOptions(options)

    uiapp.DialogBoxShowing += _suppress_connected_move_dialog
    try:
        align_connectors(moving_id, source, target)
        source.ConnectTo(target)
        transaction.Commit()
    except Exception as error:
        transaction.RollBack()
        forms.alert("Fast Connect error:\n{}".format(error))
    finally:
        uiapp.DialogBoxShowing -= _suppress_connected_move_dialog


def main():
    picked = pick_two_elements()
    if picked is None:
        return
    fixed_element, moving_element = picked

    pair = choose_connector_pair(fixed_element, moving_element)
    if pair is None:
        return
    source, target = pair

    connect(moving_element.Id, source, target)


if __name__ == "__main__":
    main()
