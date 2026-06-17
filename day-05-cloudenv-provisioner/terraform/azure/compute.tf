resource "azurerm_linux_virtual_machine" "env" {
  name                = "${local.name_prefix}-vm"
  resource_group_name = azurerm_resource_group.env.name
  location            = azurerm_resource_group.env.location
  size                = var.vm_size
  admin_username      = var.admin_username
  network_interface_ids = [azurerm_network_interface.env.id]
  tags                = local.common_tags

  admin_ssh_key {
    username   = var.admin_username
    public_key = var.ssh_public_key
  }

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "0001-com-ubuntu-server-jammy"
    sku       = "22_04-lts-gen2"
    version   = "latest"
  }
}

resource "azurerm_storage_account" "env" {
  name                     = replace("${local.name_prefix}sa", "-", "")
  resource_group_name      = azurerm_resource_group.env.name
  location                 = azurerm_resource_group.env.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  tags                      = local.common_tags

  blob_properties {
    versioning_enabled = true
  }
}
