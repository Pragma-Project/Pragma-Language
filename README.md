-------------------------------------------------------------------------------------
# PRAGMA LANGUAGE
[This Web Page is more up-to-date than this Readme file](https://pragma-project.github.io/Pragma-Language/syntax-reference.html)
-------------------------------------------------------------------------------------
Transpiles to C, uses intuitive, Java-like syntax but with more clarity and completeness

Rust is popular and has institutional backing but many complain that it has/is:
- steep learning curve
- unintuitive/confusing syntax
- frustrating to work with when total memory safety isn't important

Pragma compromises by having easier-on-the-eyes syntax than either C or Rust, and provides the same memory safety as Rust.

How?
- Mathematically-proven safety (Frama-C with the WP Plugin, which uses the same mathematical methods Rust uses to prove safety)
- Decentralized signed hash that proves the code you're looking at was mathematically proven (Blockchain technology)

So not only is your code safe, but any libraries/packages you download that are signed are also safe.  And there's a level below full safety available
where only regular sanitizers ran.

Basically the LLM's have made it where the mathematical part is now doable for everyday people - everything else was already there.  

-------------------------------------------------------------------------------------

It hashes your source file with SHA-256.  When you run the verification pipeline, every tool's full output is collected, hashed, 
and bundled into JSON alongside the source hash and tool versions.  The output is a CID officially, but it is ultimately the hash.
The hash is hosted on Pinata, which right now gives you 1 GB of space on the free tier.  The glue is Solidity, a type of smart contract on Ethereum.
Pinata sits on the IPFS network, which is just a P2P network of hashes.  Whenever someone requests the original timestamped 
hash through IPFS, it checks and finds the hosting node and downloads it.  It'll look something like this:

  "tool_results": [
    { "tool": "cbmc",     "version": "5.95.1", "passed": true,
  "output_hash": "a3f..." },
    { "tool": "asan+ubsan","version": "gcc 13.2.0", "passed": true,
  "output_hash": "b7c..." },
    { "tool": "tsan",     "version": "gcc 13.2.0", "passed": true,
  "output_hash": "d1e..." }
  ]

To verify any piece of code: hash the file yourself with sha256sum file.c, look up that hash in the on-chain registry, fetch the attestation from IPFS using the stored CID, and
optionally re-run CBMC and the sanitizers yourself if they used those.  You'll get byte-for-byte identical results.

No trust required, same safety as Rust with the option to not fight the compiler over it if you want to.

I made two modes of signed code: MemResistant and MemProof.  The former has a lot of tools perform static analysis (listed at top), while the latter does that and formally proves safety mathematically.
So you get 3 options: unsigned, signed as confidence in safety, signed as proven safe.  Gives you the ability to at least in many cases have some confidence that someone didn't bound a buffer somewhere,
to formally proven using the same math that Rust uses.  

Repository includes the following tools as flags: 
 - AOT sanitzation through A/T/UBSan
 - CBMC
 - simple custom array out-of-bounds checker
 - PGO and LTO optimization at runtime
