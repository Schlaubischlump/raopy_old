/* See: https://github.com/lperrin/node_airtunes/blob/master/src/codec.cc
Minimal wrapper to encode and aes encrypt alac data.
*/

#include <pybind11/stl.h>
#include <pybind11/pybind11.h>

#include <cstring>
#include <openssl/aes.h>
#include <openssl/engine.h>
#include <openssl/rand.h>

namespace py = pybind11;

extern "C" {
    #include "aes_utils.h"
}

#include "base64.h"

#include "alac/ALACEncoder.h"


#define kBlockSize 16
#define kFramesPerPacket 352
#define kSampleRate 44100

// These values should be changed at each iteration
static uint8_t iv [] = { 0x78, 0xf4, 0x41, 0x2c, 0x8d, 0x17, 0x37, 0x90, 0x2b, 0x15, 0xa6, 0xb3, 0xee, 0x77, 0x0d, 0x67 };
static uint8_t aes_key [] = { 0x14, 0x49, 0x7d, 0xcc, 0x98, 0xe1, 0x37, 0xa8, 0x55, 0xc1, 0x45, 0x5a, 0x6b, 0xc0, 0xc9, 0x79 };

void FillInputAudioFormat(AudioFormatDescription *format, int sample_rate) {
  format->mFormatID = kALACFormatLinearPCM;
  format->mSampleRate = sample_rate;
  format->mFormatFlags = 12;

  format->mBytesPerPacket = 4;
  format->mBytesPerFrame = 4;
  format->mBitsPerChannel = 16;
  format->mChannelsPerFrame = 2;
  format->mFramesPerPacket = 1;

  format->mReserved = 0;
}

void FillOutputAudioFormat(AudioFormatDescription *format, int frames_per_packet) {
  format->mFormatID = kALACFormatAppleLossless;
  format->mSampleRate = 44100;
  format->mFormatFlags = 1;

  format->mBytesPerPacket = 0;
  format->mBytesPerFrame = 0;
  format->mBitsPerChannel = 0;
  format->mChannelsPerFrame = 2;
  format->mFramesPerPacket = frames_per_packet;

  format->mReserved = 0;
}

std::vector<unsigned char> EncryptAES(std::vector<unsigned char> alacData) {
    // This will encrypt data in-place
    unsigned char *data = alacData.data();
    int32_t alacSize = alacData.size();

    uint8_t *buf;
    int i = 0, j;
    uint8_t *nv = new uint8_t[kBlockSize];

    aes_context ctx;
    aes_set_key(&ctx, aes_key, 128);
    memcpy(nv, iv, kBlockSize);

    while(i + kBlockSize <= alacSize) {
    buf = data + i;

    for(j = 0; j < kBlockSize; j++)
      buf[j] ^= nv[j];

    aes_encrypt(&ctx, buf, buf);
    memcpy(nv, buf, kBlockSize);

    i += kBlockSize;
    }

    return alacData;
}


PYBIND11_MODULE(libalac, m) {
    m.doc() = "Python ALACEncoder bindings.";

    py::class_<ALACEncoder> encoder(m, "ALACEncoder");

    encoder.def(py::init([](int frames_per_packet)
    {
        AudioFormatDescription outputFormat;
        FillOutputAudioFormat(&outputFormat, frames_per_packet);

        ALACEncoder *encoder = new ALACEncoder();

        encoder->SetFrameSize(frames_per_packet);
        encoder->InitializeEncoder(outputFormat);

        return encoder;
    }), py::arg("frames_per_packet")=kFramesPerPacket);

    encoder.def("encode_alac", [](ALACEncoder *encoder, std::vector<unsigned char> pcmData, int sample_rate=kSampleRate)
    {
        AudioFormatDescription inputFormat, outputFormat;
        FillInputAudioFormat(&inputFormat, sample_rate);
        FillOutputAudioFormat(&outputFormat, encoder->GetFrameSize());

        int32_t alacSize = pcmData.size();
        std::vector<unsigned char> alacData(alacSize);

        encoder->Encode(inputFormat, outputFormat, pcmData.data(), alacData.data(), &alacSize);

        return alacData;
    }, "Encode PCM data to ALAC data.", py::arg("pcmData"), py::arg("sample_rate")=kSampleRate);

    m.def("encrypt_aes", &EncryptAES, "Encrypt alac data with an aes key.", py::arg("alacData"));
}
