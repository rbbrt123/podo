resource "azurerm_virtual_network" "podo" {
  name                = "podo-vnet"
  address_space       = ["10.0.0.0/16"]
  location            = azurerm_resource_group.podo.location
  resource_group_name = azurerm_resource_group.podo.name
}

resource "azurerm_subnet" "podo" {
  name                 = "podo-subnet"
  resource_group_name  = azurerm_resource_group.podo.name
  virtual_network_name = azurerm_virtual_network.podo.name
  address_prefixes     = ["10.0.1.0/24"]
}

resource "azurerm_public_ip" "podo" {
  name                = "podo-vm-ip"
  resource_group_name = azurerm_resource_group.podo.name
  location            = azurerm_resource_group.podo.location
  allocation_method   = "Static"
  sku                 = "Standard"
}

resource "azurerm_network_security_group" "podo" {
  name                = "podo-nsg"
  location            = azurerm_resource_group.podo.location
  resource_group_name = azurerm_resource_group.podo.name

  security_rule {
    name                       = "AllowSSHFromMe"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "22"
    source_address_prefix      = var.my_ip
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "AllowPodoApp"
    priority                   = 110
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_ranges    = ["7860", "8000"]
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }
}

resource "azurerm_subnet_network_security_group_association" "podo" {
  subnet_id                 = azurerm_subnet.podo.id
  network_security_group_id = azurerm_network_security_group.podo.id
}

resource "azurerm_network_interface" "podo" {
  name                = "podo-nic"
  location            = azurerm_resource_group.podo.location
  resource_group_name = azurerm_resource_group.podo.name

  ip_configuration {
    name                          = "internal"
    subnet_id                     = azurerm_subnet.podo.id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.podo.id
  }
}