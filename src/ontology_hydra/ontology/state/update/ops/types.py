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

OperationArgs = (
    add_class.AddClassOperationArgs
    | update_class.UpdateClassOperationArgs
    | del_class.DeleteClassOperationArgs
    | add_object_property.AddObjectPropertyOperationArgs
    | update_object_property.UpdateObjectPropertyOperationArgs
    | add_data_property.AddDataPropertyOperationArgs
    | update_data_property.UpdateDataPropertyOperationArgs
    | del_property.DeletePropertyOperationArgs
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
