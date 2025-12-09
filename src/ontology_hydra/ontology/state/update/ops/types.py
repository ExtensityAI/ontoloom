from . import (
    add_class,
    add_data_property,
    add_object_property,
    del_class,
    del_property,
    update_class,
    update_data_property,
    update_object_property,
)

Operation = (
    add_class.AddClassOperation
    | update_class.UpdateClassOperation
    | del_class.DeleteClassOperation
    | add_object_property.AddObjectPropertyOperation
    | update_object_property.UpdateObjectPropertyOperation
    | add_data_property.AddDataPropertyOperation
    | update_data_property.UpdateDataPropertyOperation
    | del_property.DeletePropertyOperation
)
