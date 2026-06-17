data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }
}

resource "aws_security_group" "env_sg" {
  name        = "${local.name_prefix}-sg"
  description = "Dev/QA environment SG — SSH restricted, no public ingress beyond that."

  ingress {
    description = "SSH from the office/VPN CIDR only"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/8"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-sg" })
}

resource "aws_instance" "env" {
  ami                    = data.aws_ami.amazon_linux.id
  instance_type          = var.instance_type
  vpc_security_group_ids = [aws_security_group.env_sg.id]

  # Auto-shutdown safety net: a scheduled event (outside this module) also
  # checks the ExpiryDate tag and stops/terminates abandoned instances even
  # if the GitHub Actions teardown trigger is somehow missed.
  tags = merge(local.common_tags, { Name = "${local.name_prefix}-instance" })

  lifecycle {
    ignore_changes = [ami] # avoid noisy diffs as the latest AMI rolls forward
  }
}
