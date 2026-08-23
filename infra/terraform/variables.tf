variable "my_ip" {
  description = "Your current public IP address, in CIDR form (e.g. 1.2.3.4/32). Used to restrict SSH access to only you."
  type        = string
}