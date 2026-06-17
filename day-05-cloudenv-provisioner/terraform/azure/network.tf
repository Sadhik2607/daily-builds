resource "azurerm_virtual_network" "env" {
  name                = "${local.name_prefix}-vnet"
  address_space       = ["10.10.0.0/16"]
  location            = azurerm_resource_group.env.location
  resource_group_name = azurerm_resource_group.env.name
  tags                = local.common_tags
}

resource "azurerm_subnet" "env" {
  name                 = "${local.name_prefix}-subnet"
  resource_group_name  = azurerm_resource_group.env.name
  virtual_network_name = azurerm_virtual_network.env.name
  address_prefixes     = ["10.10.1.0/24"]
}

resource "azurerm_network_security_group" "env" {
  name                = "${local.name_prefix}-nsg"
  location            = azurerm_resource_group.env.location
  resource_group_name = azurerm_resource_group.env.name
  tags                = local.common_tags

  security_rule {
    name                       = "AllowSSHFromVPN"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "22"
    source_address_prefix      = "10.0.0.0/8"
    destination_address_prefix = "*"
  }
}

resource "azurerm_network_interface" "env" {
  name                = "${local.name_prefix}-nic"
  location            = azurerm_resource_group.env.location
  resource_group_name = azurerm_resource_group.env.name
  tags                = local.common_tags

  ip_configuration {
    name                          = "internal"
    subnet_id                     = azurerm_subnet.env.id
    private_ip_address_allocation = "Dynamic"
  }
}

resource "azurerm_network_interface_security_group_association" "env" {
  network_interface_id     = azurerm_network_interface.env.id
  network_security_group_id = azurerm_network_security_group.env.id
}
