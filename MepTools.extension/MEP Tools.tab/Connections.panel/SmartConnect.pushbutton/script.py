# -*- coding: utf-8 -*-
"""Connects two picked MEP elements: aligns their geometry and creates the connection."""

__title__ = "Smart\nConnect"
__doc__ = "Connects two picked MEP elements: aligns their geometry and creates the connection."
__author__ = "Rafal Buczynski"

import math

from Autodesk.Revit.DB import (
    Domain,
    ConnectorType,
    MEPCurve,
    FamilyInstance,
    Line,
    XYZ,
    Transaction,
    ElementTransformUtils,
)
from Autodesk.Revit.UI.Selection import ObjectType, ISelectionFilter
from Autodesk.Revit.Exceptions import OperationCanceledException
from pyrevit import revit, forms

from smart_connect import ConnectorDomain, ConnectorInfo, find_best_pair

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


def get_free_connectors(element):
    manager = None
    if isinstance(element, MEPCurve):
        manager = element.ConnectorManager
    elif isinstance(element, FamilyInstance) and element.MEPModel is not None:
        manager = element.MEPModel.ConnectorManager
    if manager is None:
        return []
    return [c for c in manager.Connectors
            if c.ConnectorType == ConnectorType.End and not c.IsConnected]


def to_info(connector, index):
    origin = connector.Origin
    size = 0.0
    try:
        size = connector.Radius * 2.0
    except Exception:
        pass  # non-round connector
    domain = DOMAIN_MAP.get(connector.Domain, ConnectorDomain.UNDEFINED)
    return ConnectorInfo(index, origin.X, origin.Y, origin.Z, domain, size)


def align_connectors(moving_id, source, target):
    """Rotate and move the moving element so its source connector coincides with
    the target connector and faces it head-on (the connector axes point at each other)."""
    source_dir = source.CoordinateSystem.BasisZ          # outward direction of the connector
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


def main():
    selection_filter = MepConnectableFilter()
    try:
        reference_fixed = uidoc.Selection.PickObject(
            ObjectType.Element, selection_filter, "Pick the first element (stays in place).")
        reference_moving = uidoc.Selection.PickObject(
            ObjectType.Element, selection_filter, "Pick the second element (will be moved).")
    except OperationCanceledException:
        return

    fixed_element = doc.GetElement(reference_fixed)
    moving_element = doc.GetElement(reference_moving)

    free_fixed = get_free_connectors(fixed_element)
    free_moving = get_free_connectors(moving_element)
    if not free_fixed or not free_moving:
        forms.alert("At least one element has no free connectors.")
        return

    infos_fixed = [to_info(c, i) for i, c in enumerate(free_fixed)]
    infos_moving = [to_info(c, i) for i, c in enumerate(free_moving)]

    match = find_best_pair(infos_fixed, infos_moving, SIZE_TOLERANCE_FEET)
    if match is None:
        forms.alert("No compatible connector pair found (different domain or size).")
        return

    target = free_fixed[match[0].source_index]   # fixed
    source = free_moving[match[1].source_index]  # moving

    transaction = Transaction(doc, "Smart Connect MEP")
    transaction.Start()
    try:
        align_connectors(moving_element.Id, source, target)
        source.ConnectTo(target)
        transaction.Commit()
    except Exception as error:
        transaction.RollBack()
        forms.alert("Smart Connect error:\n{}".format(error))


if __name__ == "__main__":
    main()
