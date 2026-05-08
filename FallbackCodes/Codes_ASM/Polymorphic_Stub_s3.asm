comment #
Name: Not-Satan
Author: Twizted / Immortal Riot
Date: May 1998

Description:
This is my attempt at writing an "anti-anti-virus" virus. I was very bored
with my other viruses and wanted to make something that would test the boundaries
of what is possible with virus writing. This virus is not really optimised. It's
just to demonstrate some new ideas. The code is divided in several parts, so
it's easier to understand.

First of all this virus is selfencrypted. The encryption key itself changes (a
random value between 0 and 255), as well as the encryption algorithm used. The
encryption algorithms are random too. The virus contains about 400 bytes of
encrypted code. There are only 367 bytes of code, but the virus is 1024 bytes.
The rest is filled with NOPs. When the virus is decrypted there is also another
part of the code (called DELTA) which decodes the location where the virus will
be executed from. It's also encrypted. This part of code is placed right before
the virus code.

When the decrypted code is run it checks wether it's running under Win95 or
WinNT by looking at the kernel name. If it's found the virus will hook int1 vector
and display its text:

   Not-Satan v1.0 by Twizted/Ir [19/05/1998]

If no debugger is detected the virus will return control to the host program,
otherwise it will execute int3 which should trigger the debugger. Under NT it
will search for NTVDM.EXE and then again return control to the host program if
found. If not found, it will write into its header field entry point 00000002.
This is quite dangerous because all NT EXEs have entry point 00000000 and they
are loaded at address 00400000h. So we can assume that the first function any
EXE wants to call is located there. By changing the entry point to 02h, the
first instruction that will be executed when an infected NT EXE is started will
be rep retf; i.e.: RETF; RETF; etc.

All this happens under int1 handling routine, so even if the user tries to
disable int1 via software interrupt disabling routines, he will still get
his system destabilized.

Under Win95 the virus searches for KERNEL32.DLL, loads its base address and
then searches for the Export Table in it. Then it hooks int1 as above and
disables the Write Protect bit in CR0 register. After that, it returns control
to the host program. Later on it may use API functions, but until now it has
not needed them anymore. However, this feature was added later on, so the code
wasn't changed in order to save space.

After the virus has been executed, the Delta Code decrypts itself and jumps
into it. In the delta code the actual starting address of the virus is decoded
and then the virus runs some sanity checks on the memory layout and then
returns control to the host program.

In case of WinNT, the virus cannot directly access the physical memory. Instead
it writes the code into its stack (this works because all threads share one
stack area in NT). Then, after the code has been copied to the stack, it disables
write protection in CR0 and executes it.

The code in the stack does two things:
- Returns control to host program.
- Displays message.

Because the stack is writable only for the thread which created it, the virus
cannot execute the stack code. To do this, the main code copies the stack code
into its own stack and makes an exception handler jump into it. Because the
main code runs in the same stack area, the exception handler can change its
permissions and then run the code.

The stack code contains a REP RETF instruction sequence (at least 400 times),
so it should crash the system (if executed). However, it doesn't. This is due
to the fact that if the system is already unstable, executing REP RETF will not
make it better. This time, it just doesn't make it worse.

As you can see, this code needs many layers of obfuscation. For example, the
virus could be written like this:

1. Decrypt virus with random algorithm -> CODE
2. Run CODE
3. CODE:
   Decode delta code -> DELTA
   Jump to DELTA
4. DELTA:
   Calculate virus starting position
   Check for OS (WIN95/NT)
   Hook int1, disable write protection
   Return to host program

The code is encrypted only once with random parameters -> CODE. Now, we need
another layer of encryption. We need to calculate the virus starting position
after the delta code has been decoded. The delta code is encrypted, so we
cannot simply add its size to the offset of the start of CODE. But we can use
a variable X which is set to the calculated offset. Then we encrypt X with yet
another random algorithm and put it inside the delta code. When the delta code
is run, it gets the current position of X, decrypts it and adds to its current
offset. Now we have the real virus starting position and we jump to there.
This approach is called double encryption. You can create more layers if you
like. For example, the delta code could be also encrypted using another random
algorithm. Then the code that reads its code and decrypts it would look something
like this:

1. Get current position P
2. Decrypt P + X with random algorithm
3. Add result to P and jump there.

Now, after we have jumped to the decrypted virus code, we have to go through
another decryption procedure and then we will reach the real start. Or we don't
need to do the decryption at all. Instead, we could create a variable which holds
an offset relative to the current position P. Then we would set it to V, where
V is the offset of the code that will be run last (in our case, it would be the
hooked int1 code). We could then replace these lines:

P = Get_Call_Address();
Jump_To_Virus_Code(P);

With this:

RelativeOffset = SomeValue;
P = Get_Call_Address();
V = RelativeOffset + P;

And finally we can run the code:

Jump_To_Virus_Code(V);

Then we do not need to decrypt anything. All we need to do is to calculate
the correct relative offset and then to place it in a variable. But how to do
that? Well, we know that the code that will be run last is located somewhere in
the virus code. So we can simply subtract the positions and we will get the
relative offset:

RelativeOffset = VirusCodeEnd - Get_Call_Address();

However, this code does not have to be in the end of the virus code. We can
use any other code. But then, we must take care of the correct positioning. Let's
say we want to run the last code right after the decrypted delta code. We can
then calculate its position like this:

P = Get_Call_Address();
RelativeOffset = VirusCodeStart + DeltaCodeSize + 1;

We can see that the calculation is almost the same. Only thing we have to add
here is the size of the delta code. And we can also use PUSH instead of setting
up the variable, so the code could look like this:

P = Get_Call_Address();
Push(DeltaCodeSize + 1);
Add(Eax,P);
Call(Eax);

But there is nothing stopping us from using a SUB instead of ADD here. That way
we could use PUSH only and the code would look like this:

P = Get_Call_Address();
Sub(Eax,P);
Push(Eax);
Call(Eax);

See? We have got rid off the ADD command and everything is ok. We could continue
and remove the Call, too. Then we would get:

DeltaCodeStartPosition = Get_Call_Address() + DeltaCodeSize + 1;
Jump_To_Virus_Code(DeltaCodeStartPosition);

Or something similar. The code above shows that we do not need to decrypt anything.
Instead, we can calculate the correct offset and then run the code. This idea
can be enhanced further and you can use variables that hold offsets, but you
do not have to calculate their values yourself. You could simply use something
like this:

Run_Jump(CodeToBeExecuted);

This macro calculates the offset for you and then runs the code. Of course,
all this must be implemented inside the macros so you cannot access the code
directly.

Another enhancement of this method is to generate a lot of different variables
inside the delta code. The code that decrypts the delta code could be encrypted
several times using different methods. Each time you could use a different
variable to store the offset of the decrypted code. Finally, you could use
something like this:

Decrypt_Delta_Code_Using_Random_Algorithm(Variable1);
... (other code)
CalculateOffset(Variable2);
Run_Jump(Variable1 + Variable2);

This way, it becomes difficult to follow the flow of execution inside the delta
code. The code that calculates the offset might be run before the code that
decrypts the delta code. However, it does not matter, because the final result
must be stored somewhere anyway. So why not use several variables?

Well, enough talk. Let's see how this virus works:


INFECTED FILE:
===========================
. . .
0102BEEC: B8800