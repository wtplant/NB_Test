FIELD_CHOICES = {
    'dcim.Device.status': (
        ('active', 'Active', 'green'),
        ('planned', 'Planned', 'cyan'),
        ('staged', 'Staged', 'blue'),
        ('maintenance', 'Maintenance', 'red'),
        ('inventory', 'Inventory', 'yellow'),
        ('provisioned', 'Provisioned', 'orange'),
        ('decommissioning', 'Decommissioing', 'purple'),
        ('decommissioned', 'Decommissioned', 'black')
    ),
}
