# Synology VMM to a Linux guest: temporary USB ownership

The case-study host reliably enumerated CP2102N **`10c4:ea60`** while the Mac
transport was unreliable. That exact USB device was attached temporarily to a
Linux VM through VMM's libvirt tooling. Driver installation occurred **inside
the guest**; DSM kernel modules were not changed.

[Synology lists USB passthrough](https://www.synology.com/en-global/dsm/7.3/software_spec/vmm)
for ordinary VMM guests, but not Virtual DSM. Availability depends on the
installed VMM release. This is a record and template for the observed admin
workflow, not a claim that arbitrary USB serial hardware is supported by every
Synology model or UI version.

## Identify exactly one device and VM

On the host, inspect USB enumeration and the intended VM using VMM's packaged
`virsh`. Resolve that executable's path for your installation; do not substitute
an unrelated libvirt instance. For example, with operator-supplied values:

```sh
VMM_VIRSH=/replace/with/vmm/virsh
FLASH_VM=replace-with-existing-linux-vm
lsusb -d 10c4:ea60
sudo "$VMM_VIRSH" list --all
```

The observed VMM binary was
`/var/packages/Virtualization/target/usr/local/bin/virsh`. Check that path on
your installation before assigning it to `VMM_VIRSH`.

Confirm the physical adapter, USB identity, and selected VM. Vendor/product
alone may match multiple adapters. Record its current USB **bus and device**
numbers; those can change after unplugging. Prepare a private hostdev XML using
the identified decimal numbers rather than selecting a whole USB controller:

```xml
<hostdev mode='subsystem' type='usb' managed='yes'>
  <source>
    <vendor id='0x10c4'/>
    <product id='0xea60'/>
    <address bus='REPLACE_BUS_NUMBER' device='REPLACE_DEVICE_NUMBER'/>
  </source>
  <alias name='ua-slzb-core-upgrade'/>
  <address type='usb' bus='REPLACE_GUEST_XHCI_CONTROLLER_INDEX' port='REPLACE_FREE_GUEST_PORT'/>
</hostdev>
```

The source bus/device identifies the **host** USB device. The final address
selects an existing **guest** USB controller and a free port. Inspect the VM's
current XML privately to identify its xHCI controller and unused port; do not
copy another machine's index or port. No new persistent controller is added.
An initial default UHCI assignment and a later xHCI assignment both experienced
transfer failures in this session, so xHCI alone was not proven to fix them.

The placeholder XML is deliberately not executable until reviewed. Save the
completed file privately as `cp210x-usb.xml`. Then attach to the running guest:

```sh
sudo "$VMM_VIRSH" attach-device "$FLASH_VM" cp210x-usb.xml --live
```

`--live` changes the running VM only; this workflow does not use `--config` or
create a persistent assignment. The host and another guest must not use the
same device concurrently. The [libvirt attach-device reference](https://www.libvirt.org/manpages/virsh.html#attach-device)
describes these scopes. If your VMM requires an explicit connection URI, use
the URI of its existing daemon rather than guessing.

## Load the guest's matching USB serial driver

Inside the Ubuntu guest, check that the device arrived and identify the running
kernel and available module:

```sh
lsusb -d 10c4:ea60
uname -r
modinfo cp210x
```

In the observed guest, kernel `6.8.0-142-generic` lacked `cp210x` until the
official matching `linux-modules-extra` package was installed. The general
command uses the **running** kernel, not a copied version string:

```sh
sudo apt-get update
sudo apt-get install "linux-modules-extra-$(uname -r)"
sudo modprobe cp210x
ls -l /dev/serial/by-id/
```

This loaded the driver without a guest reboot in the observed setup. Do not
install an unrelated kernel or force a module built for another kernel. Other
Linux distributions package modules differently. If `modinfo` already succeeds,
the package installation may be unnecessary.
The matching package installation completed without service/container restarts.

Confirm the new serial port belongs to the selected device and that no other
process owns it. Prefer its stable `/dev/serial/by-id/` link when available.
Use the guest's serial permissions or an existing administrative access method;
do not make the device world-writable or indiscriminately kill serial services.
Then follow the [guarded snapshot and core migration guide](usb-core-upgrade.md).

## Detach the temporary assignment

After the flasher exits and verification is complete, close guest serial users
and run on the host:

```sh
sudo "$VMM_VIRSH" detach-device "$FLASH_VM" cp210x-usb.xml --live
```

Confirm the VM no longer owns this USB device. If USB bus/device numbers changed,
inspect the VM's current hostdev assignment and detach that exact assignment;
do not remove an unrelated device to make the command succeed. No host-module
installation, VM reboot, or persistent VMM configuration change is part of this
temporary path.

The actual attachment was removed after write and boot verification, with no
USB hostdevs remaining on the VM. The matching guest kernel-module package was
retained; DSM host modules and persistent VM configuration remained unchanged.
