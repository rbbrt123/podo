resource "azurerm_linux_virtual_machine" "podo" {
  name                = "podo-vm"
  resource_group_name = azurerm_resource_group.podo.name
  location            = azurerm_resource_group.podo.location
  size                = "Standard_B1s"
  admin_username      = "azureuser"

  network_interface_ids = [
    azurerm_network_interface.podo.id,
  ]

  admin_ssh_key {
    username   = "azureuser"
    public_key = file(pathexpand("~/.ssh/podo_vm_ed25519.pub"))
  }

  disable_password_authentication = true

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "ubuntu-24_04-lts"
    sku       = "server"
    version   = "latest"
  }

  custom_data = filebase64("${path.module}/cloud-init.yaml")
}

