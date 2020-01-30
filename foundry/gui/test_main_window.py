from PySide2.QtCore import QPoint
from PySide2.QtGui import Qt


def test_open(main_window):
    pass


def test_middle_click_adds_object(main_window, qtbot):
    # GIVEN the level_view and that the object dropdown has an object selected
    level_view = main_window.level_view

    assert main_window.object_dropdown.currentIndex() > -1

    # WHEN a middle click happens in the level view without an object present
    pos = QPoint(100, 100)

    assert level_view.object_at(*pos.toTuple()) is None

    qtbot.mouseClick(main_window, Qt.MiddleButton, pos=pos)

    # THEN there is now the selected object
    domain, object_index = main_window.object_dropdown.currentData(Qt.UserRole)

    new_object = level_view.object_at(*pos.toTuple())

    assert new_object is not None
    assert new_object.domain == domain
    assert new_object.obj_index == object_index
